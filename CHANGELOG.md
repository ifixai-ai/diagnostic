# Changelog

All notable changes to `ifixai` will be recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[SemVer](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **C1 — Template variable substitution in rubric judge prompts.** `build_judge_prompt` now substitutes `{placeholder}` variables (e.g. `{policy_context}`, `{source_material}`, `{system_instructions}`) before sending the rubric template to the judge. Previously these were passed verbatim, so the judge saw literal placeholder text instead of real data. Affects B07–B09, B11–B14. New public function `render_judge_prompt_template` handles substitution via regex (JSON-style braces are never matched). Each affected runner now supplies the relevant context variables at call time.

## [1.0.0] — 2026-04-27

Initial public release.
