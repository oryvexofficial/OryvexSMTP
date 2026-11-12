# frozen_string_literal: true

class SMTPSender

  def logger
    Postal.logger
  end

  attr_reader :domain
  attr_reader :endpoints
  attr_reader :current_endpoint
  attr_reader :connection_errors

  # Initialize a new SMTPSender for the given domain.
  #
  # @param domain [String] the domain to send to
  # @param servers [Array<SMTPClient::Server>] a list of servers to use (default: nil, will resolve)
  # @param source_ip_address [IPAddress] the source IP address to use for this sender
  def initialize(domain, source_ip = nil, servers: nil, source_ip_address: nil, rcpt_to: nil)
    @domain = domain
    @servers = servers
    @source_ip_address = source_ip_address || source_ip
    @rcpt_to = rcpt_to
    @endpoints = []
    @connection_errors = []
  end

  def start
    servers = @servers || self.class.smtp_relays || resolve_mx_records_for_domain || []

    servers.each do |server|
      server.endpoints.each do |endpoint|
        result = connect_to_endpoint(endpoint)
        return endpoint if result
      end
    end

    false
  end

  def send_message(message)
    # If we don't have a current endpoint than we should raise an error.
    if @current_endpoint.nil?
      return create_result("SoftFail") do |r|
        r.retry = true
        r.details = "No SMTP servers were available for #{@domain}."
        if @endpoints.empty?
          r.details += " No hosts to try."
        else
          hostnames = @endpoints.map { |e| e.server.hostname }.uniq
          r.details += " Tried #{hostnames.to_sentence}."
        end
        r.output = @connection_errors.join(", ")
        r.connect_error = true
      end
    end

    mail_from = determine_mail_from_for_message(message)
    raw_message = message.raw_message

    # Add a Resent-Sender header only when Postal is configured to do so.
    if Postal::Config.postal.use_resent_sender_header?
      raw_message = "Resent-Sender: #{mail_from}\r\n" + raw_message
    end

    begin
      @current_endpoint.send_message(raw_message, mail_from, @rcpt_to || message.rcpt_to)
      create_result("Sent") do |r|
        r.details = "Message sent to #{@current_endpoint} for #{message.rcpt_to}"
      end
    rescue Net::SMTPUnknownError, Net::SMTPServerBusy => e
      create_result("SoftFail") do |r|
        r.details = "Temporary SMTP delivery error when sending to #{@current_endpoint}: #{e.message}"
        r.output = e.message
        r.retry = true
      end
    rescue Net::SMTPFatalError => e
      create_result("HardFail") do |r|
        r.details = "Permanent SMTP delivery error when sending to #{@current_endpoint}: #{e.message}"
        r.output = e.message
      end
    rescue StandardError => e
      create_result("SoftFail") do |r|
        r.details = "An error occurred while sending the message to #{@current_endpoint}: #{e.class} (#{e.message})"
        r.output = e.message
        r.retry = true
      end
    end
  end

  def finish
    @endpoints.each(&:finish_smtp_session)
    @endpoints = []
    @current_endpoint = nil
  end

  # Determine what MAIL FROM should be used for this message. If the message's server
  # has a return path domain, we will use that. Otherwise we'll fallback to the default
  # return path domain for the application.
  #
  # @param message [QueuedMessage]
  # @return [String]
  def determine_mail_from_for_message(message)
    domain = message.domain

    return_path_domain = if domain&.use_for_any?
                           domain.return_path_domain
                         elsif domain&.verified?
                           domain.return_path_domain
                         else
                           Postal::Config.dns.return_path_domain
                         end

    "#{message.server.token}@#{return_path_domain}"
  end

  # Create a SendResult object for the given status
  #
  # @param status [String]
  # @return [SendResult]
  def create_result(status, &block)
    SendResult.new.tap do |r|
      r.type = status
      r.secure = @current_endpoint&.smtp_client&.secure_socket? || false
      block.call(r) if block_given?
    end
  end

  # Return an array of server hostnames which should receive this message
  # Direct delivery to recipient MX hosts uses port 25 by default.
  #
  # @return [Array<SMTPClient::Server>]
  def resolve_mx_records_for_domain
    outbound_port = (ENV["POSTAL_OUTBOUND_SMTP_PORT"] || 25).to_i
    ssl_mode = ENV["POSTAL_OUTBOUND_SSL_MODE"] || SMTPClient::SSLModes::AUTO
    hostnames = DNSResolver.local.mx(@domain, raise_timeout_errors: true).map(&:last)
    return [SMTPClient::Server.new(@domain, port: outbound_port, ssl_mode: ssl_mode)] if hostnames.empty?

    hostnames.map { |hostname| SMTPClient::Server.new(hostname, port: outbound_port, ssl_mode: ssl_mode) }
  end

  # Attempt to begin an SMTP sesssion for the given endpoint. If successful, this endpoint
  # becomes the current endpoints for the SMTP sender.
  #
  # Returns true if the session was established.
  # Returns false if the session could not be established.
  #
  # @param endpoint [SMTPClient::Endpoint]
  # @return [Boolean]
  def connect_to_endpoint(endpoint, allow_ssl: true)
    if @source_ip_address && @source_ip_address.ipv6.blank? && endpoint.ipv6?
      # Don't try to use IPv6 if the IP address we're sending from doesn't support it.
      return false
    end

    # Add this endpoint to the list of endpoints that we have attempted to connect to
    @endpoints << endpoint unless @endpoints.include?(endpoint)

    endpoint.start_smtp_session(allow_ssl: allow_ssl, source_ip_address: @source_ip_address)
    logger.info "Connected to #{endpoint}"
    @current_endpoint = endpoint

    true
  rescue StandardError => e
    # Disconnect the SMTP client if we get any errors to avoid leaving
    # a connection around.
    endpoint.finish_smtp_session

    # If we get an SSL error, we can retry a connection without
    # ssl.
    if e.is_a?(OpenSSL::SSL::SSLError) && endpoint.server.ssl_mode == "Auto"
      logger.warn "SSL error connecting to #{endpoint} (#{e.message}), retrying without SSL"
      return connect_to_endpoint(endpoint, allow_ssl: false)
    end

    logger.warn "Error connecting to #{endpoint}: #{e.class} (#{e.message})"
    @connection_errors << "#{endpoint} (#{e.message})"
    false
  end

  class << self

    # Return an array of SMTP relays as configured. Returns nil
    # if no SMTP relays are configured.
    #
    def smtp_relays
      return @smtp_relays if instance_variable_defined?("@smtp_relays")

      relays = Postal::Config.postal.smtp_relays
      return nil if relays.nil?

      relays = relays.filter_map do |relay|
        next unless relay.host.present?

        SMTPClient::Server.new(relay.host, port: relay.port || 587, ssl_mode: relay.ssl_mode)
      end

      @smtp_relays = relays.empty? ? nil : relays
    end

  end

end
