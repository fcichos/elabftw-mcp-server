# Changelog

All notable changes to the eLabFTW MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Owner filtering support for experiments and items (resources)
  - Added `owner` parameter to `list_experiments` tool
  - Added `owner` parameter to `list_items` tool
  - Owner parameter accepts single user ID (e.g., "2") or comma-separated multiple IDs (e.g., "2,3")
  - Added `owner` (userid) and `owner_name` (fullname) fields to experiment and item list outputs
  - Updated tool descriptions to reflect new filtering capability

### Changed
- Enhanced experiment listing output to include owner information (userid and fullname)
- Enhanced item listing output to include owner information (userid and fullname)

### Fixed
- Improved filtering capabilities for experiments and items by owner/author

## Notes

The owner filtering feature allows users to filter experiments and items by their creator/owner using the elabFTW API's native `owner` query parameter. This is particularly useful in team environments where multiple users create entries and you need to view only entries from specific users.

Example usage:
- Filter experiments by single owner: `owner="5"`
- Filter experiments by multiple owners: `owner="5,8,12"`
