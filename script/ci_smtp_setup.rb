#!/usr/bin/env ruby
# frozen_string_literal: true

require_relative "../config/environment"
require "securerandom"
require "json"

server_mode = ENV.fetch("POSTAL_CI_SERVER_MODE", "Live")
org_permalink = ENV.fetch("POSTAL_CI_ORG", "ci")
server_permalink = ENV.fetch("POSTAL_CI_SERVER", "smtp")
credential_key = ENV.fetch("POSTAL_CI_CREDENTIAL_KEY", "postal-ci-key")
domain_name = ENV.fetch("POSTAL_CI_DOMAIN", "postal-ci.local")
abort "SMTP test credential must not be empty" if credential_key.empty?

owner = User.find_or_create_by!(email_address: "ci-owner@#{domain_name}") do |user|
  user.first_name = "Oryvex"
  user.last_name = "CI"
  user.password = SecureRandom.hex(32)
  user.time_zone = "UTC"
end

org = Organization.find_or_create_by!(permalink: org_permalink) do |organization|
  organization.name = "OryvexSMTP CI"
  organization.time_zone = "UTC"
  organization.owner = owner
end

server = org.servers.find_or_create_by!(permalink: server_permalink) do |s|
  s.name = "OryvexSMTP CI"
  s.mode = server_mode
end
server.update_columns(mode: server_mode) unless server.mode == server_mode

domain = org.domains.find_or_create_by!(name: domain_name) do |d|
  d.verification_method = "DNS"
  d.verified_at = Time.current
end
domain.update_columns(verified_at: Time.current) unless domain.verified_at

credential = server.credentials.find_by(type: "SMTP", name: "CI SMTP Key")
credential ||= server.credentials.create!(type: "SMTP", name: "CI SMTP Key")
other = Credential.where(type: "SMTP", key: credential_key).where.not(id: credential.id)
abort "Configured SMTP test credential is already in use" if other.exists?
credential.update_columns(key: credential_key) unless credential.key == credential_key

puts "OryvexSMTP CI initialized in #{server_mode} mode."
puts "SMTP username: #{org_permalink}/#{server_permalink}; runner port: 2525"
puts "Sender domain: #{domain.name} (verified)"

# Write DNS record details to /config/dns_records.json
begin
  dns_data = {
    domain: domain.name,
    spf_record: domain.spf_record,
    dkim_name: domain.dkim_record_name,
    dkim_record: domain.dkim_record,
    dmarc_name: "_dmarc.#{domain.name}",
    dmarc_record: "v=DMARC1; p=none; rua=mailto:postmaster@#{domain.name}",
    return_path_domain: domain.return_path_domain,
    return_path_target: Postal::Config.dns.return_path_domain
  }
  File.write("/config/dns_records.json", JSON.pretty_generate(dns_data))
  puts "DNS setup exported to /config/dns_records.json"
rescue => e
  puts "Notice: Could not write dns_records.json: #{e.message}"
end
