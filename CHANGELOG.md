# Changelog

## [1.1.2](https://github.com/CrashLoopBackCoffee/th-strava-sensor/compare/v1.1.1..v1.1.2) - 2025-08-20

### 🐛 Bug Fixes

* fix: convert Docker repository name to lowercase in release workflow by @tobiashenkel in [#75](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/75)

## [1.1.1](https://github.com/CrashLoopBackCoffee/th-strava-sensor/compare/v1.1.0..v1.1.1) - 2025-08-19

### 🐛 Bug Fixes

* fix: convert Docker repository name to lowercase by @tobiashenkel in [#73](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/73)

### 🔧 Other Changes

* chore: prepare release v1.1.1 by @tobiashenkel in [#72](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/72)

## [1.1.0](https://github.com/CrashLoopBackCoffee/th-strava-sensor/compare/v1.0.0..v1.1.0) - 2025-08-19

### ✨ Enhancements

* feat: add Docker containerization with multi-stage build and CI/CD by @tobiashenkel in [#67](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/67)

### 🐛 Bug Fixes

* fix: sync uv.lock with version bump in changelog workflow by @tobiashenkel in [#71](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/71)
* Improve webhook server error handling and documentation by @tobiashenkel in [#70](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/70)

### 🔧 Other Changes

* chore: prepare release v1.1.0 by @tobiashenkel in [#64](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/64)
* chore(deps): update docker/build-push-action action to v6 by @tobiashenkel in [#69](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/69)
* chore(deps): update ghcr.io/astral-sh/uv docker tag to v0.8.12 by @tobiashenkel in [#68](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/68)
* Fix pre-commit validation by @tobiashenkel in [#66](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/66)
* fix: make bump detection more robust by removing emoji dependency by @tobiashenkel in [#65](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/65)
* chore(deps): update kenji-miyake/setup-git-cliff action to v2 by @tobiashenkel in [#63](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/63)

## [1.0.0](https://github.com/CrashLoopBackCoffee/th-strava-sensor/compare/v0.1.4..v1.0.0) - 2025-08-18

### 🚨 Breaking Changes

* Add strava webhook support by @tobiashenkel in [#24](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/24)

### 🐛 Bug Fixes

* fix: update release workflow to use proper semantic versioning by @tobiashenkel in [#62](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/62)

### 🔧 Other Changes

* chore: prepare release v1.0.0 by @tobiashenkel in [#61](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/61)
* chore(deps): lock file maintenance by @tobiashenkel in [#56](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/56)
* chore(deps): update kenji-miyake/setup-git-cliff action to v2 by @tobiashenkel in [#60](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/60)
* chore: prepare release v1.0.0 by @tobiashenkel in [#55](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/55)
* fix: use setup-git-cliff for proper git-cliff installation by @tobiashenkel in [#59](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/59)
* fix: install git-cliff before running bump detection script by @tobiashenkel in [#58](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/58)
* feat: add semantic version bump detection script by @tobiashenkel in [#57](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/57)

## [0.1.4](https://github.com/CrashLoopBackCoffee/th-strava-sensor/compare/v0.1.3..v0.1.4) - 2025-08-15

### 🐛 Bug Fixes

* Use git cliff --unreleased by @tobiashenkel in [#54](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/54)
* Only show the latest release in github release by @tobiashenkel in [#53](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/53)

### 🔧 Other Changes

* chore: prepare release v0.1.4 by @tobiashenkel in [#52](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/52)

## [0.1.3](https://github.com/CrashLoopBackCoffee/th-strava-sensor/compare/v0.1.2..v0.1.3) - 2025-08-15

### 🐛 Bug Fixes

* fix: remove duplicate headers in GitHub release body by @tobiashenkel in [#51](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/51)

### 🔧 Other Changes

* chore: prepare release v0.1.3 by @tobiashenkel in [#50](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/50)

## [0.1.2](https://github.com/CrashLoopBackCoffee/th-strava-sensor/compare/v0.1.1..v0.1.2) - 2025-08-15

### 🐛 Bug Fixes

* fix: prevent double 'v' prefix in release workflow tag creation by @tobiashenkel in [#48](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/48)

### 🔧 Other Changes

* chore: prepare release v0.1.2 by @tobiashenkel in [#47](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/47)
* fix: remove 'v' prefix from pyproject.toml version in changelog workflow by @tobiashenkel in [#49](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/49)

## [0.1.1](https://github.com/CrashLoopBackCoffee/th-strava-sensor/compare/v0.1.0..v0.1.1) - 2025-08-15

### 🔧 Other Changes

* chore: prepare release v0.1.1 by @tobiashenkel in [#45](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/45)
* fix: improve changelog formatting in git-cliff config by @tobiashenkel in [#46](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/46)
* chore(deps): lock file maintenance by @tobiashenkel in [#22](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/22)
* chore(deps): update actions/checkout action to v5 by @tobiashenkel in [#23](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/23)

## [0.1.0] - 2025-08-15

### ✨ Enhancements

* fix: only update open PRs in changelog workflow by @tobiashenkel in [#40](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/40)
* feat: add manual trigger and improve release workflow by @tobiashenkel in [#36](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/36)
* feat: improve release workflow with git-cliff-action outputs by @tobiashenkel in [#35](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/35)
* feat: add automated changelog generation workflow by @tobiashenkel in [#31](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/31)
* Refactor direnv for multi-developer setup by @tobiashenkel in [#30](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/30)
* Skip direnv if service account token already exists by @tobiashenkel in [#26](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/26)
* Support Strava as meta source by @tobiashenkel in [#11](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/11)
* Support garmin connect by @tobiashenkel in [#10](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/10)
* Add mqtt publishing by @tobiashenkel in [#6](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/6)

### 🐛 Bug Fixes

* fix: use --bump instead of --latest in release workflow by @tobiashenkel in [#44](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/44)

### 📖 Documentation

* Analyze and document project structure with comprehensive documentation by @tobiashenkel in [#16](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/16)

### 🔧 Other Changes

* chore: prepare release 0.1.0 by @tobiashenkel in [#43](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/43)
* chore: prepare release 0.1.0 by @tobiashenkel in [#41](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/41)
* Remove surplus empty line from changelog by @tobiashenkel in [#42](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/42)
* Use pat to create release by @tobiashenkel in [#39](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/39)
* Linters should run on pull requests by @tobiashenkel in [#38](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/38)
* refactor: remove labeled trigger since it doesn't work for merged PRs by @tobiashenkel in [#37](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/37)
* Reset version by @tobiashenkel in [#33](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/33)
* feat: make Claude Code review workflow comment-triggered by @tobiashenkel in [#32](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/32)
* Optimize direnv 1Password credential loading by @tobiashenkel in [#29](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/29)
* Add initial claude memory by @tobiashenkel in [#28](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/28)
* Add claude GitHub actions 1755201497125 by @tobiashenkel in [#25](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/25)
* Add initial copilot instructions by @tobiashenkel in [#21](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/21)
* Add GitHub Copilot agent support with streamlined setup action and workflow by @tobiashenkel in [#18](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/18)
* Lock file maintenance by @tobiashenkel in [#14](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/14)
* Cleanup StravaSource by @tobiashenkel in [#13](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/13)
* Inject strava client to StravaSource by @tobiashenkel in [#12](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/12)
* Enhance logging by @tobiashenkel in [#8](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/8)
* Cleanup envrc by @tobiashenkel in [#7](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/7)
* Move cli into main package by @tobiashenkel in [#5](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/5)
* Run tests in actions by @tobiashenkel in [#4](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/4)
* Add fitfile parsing by @tobiashenkel in [#3](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/3)
* Add run-all-checks script by @tobiashenkel in [#2](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/2)
* Initialize project by @tobiashenkel in [#1](https://github.com/CrashLoopBackCoffee/th-strava-sensor/pull/1)
