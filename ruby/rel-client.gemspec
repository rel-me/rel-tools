# frozen_string_literal: true

require_relative "lib/rel/version"

Gem::Specification.new do |spec|
  spec.name = "rel-client"
  spec.version = REL::VERSION
  spec.authors = ["REL"]
  spec.email = ["support@rel.me"]

  spec.summary = "Ruby client for the REL RPC v1 API"
  spec.description = "A dependency-free Ruby client for controlling REL's persistent Chromium sessions over its loopback RPC v1 API."
  spec.homepage = "https://rel.me"
  spec.license = "MIT"
  spec.required_ruby_version = ">= 3.1"

  spec.metadata = {
    "homepage_uri" => spec.homepage,
    "source_code_uri" => "https://github.com/rel-me/rel-tools/tree/main/ruby",
    "documentation_uri" => "https://docs.rel.me/ruby/",
    "changelog_uri" => "https://github.com/rel-me/rel-tools/releases"
  }

  spec.files = Dir.chdir(__dir__) do
    Dir["lib/**/*.rb", "README.md", "LICENSE"]
  end
  spec.require_paths = ["lib"]
end
