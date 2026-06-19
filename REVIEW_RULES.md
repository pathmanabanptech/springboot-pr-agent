# Review Rules

This file is loaded by the PR review agent on every pull request.
Copy it to the root of any repo that uses this agent and edit for your team.
Rules here apply in addition to the built-in Java/SpringBoot rules.

---

## Naming conventions
- Service classes must end with `Service`
- Controller classes must end with `Controller`
- Repository interfaces must end with `Repository`
- DTO classes must end with `DTO`, `Request`, or `Response`
- Exception classes must end with `Exception`

## Layering
- Controllers call Services only — never Repositories directly
- Services call Repositories and other Services
- No business logic in `@Entity` classes

## API design
- All endpoints versioned: `/api/v1/...`
- All response bodies use the project's `ApiResponse<T>` wrapper
- Error responses use `ErrorResponse` — no raw strings or plain maps

## Logging
- Use `@Slf4j` (Lombok) — no manual `Logger` declarations
- INFO for business events, DEBUG for internal state
- Never log passwords, tokens, card numbers, or PII field values

## Configuration
- All configurable values via `@ConfigurationProperties` or `@Value`
- No hardcoded ports, timeouts, or URLs — use `application.properties`
- Secrets via environment variables or a secrets manager only

## Testing
- Every new public `@Service` method needs at least one unit test
- Unit tests: `@ExtendWith(MockitoExtension.class)` only
- Integration tests (full context): `src/test/java/integration/` only
- Minimum per service method: one happy-path + one exception test

## Dependencies
- New Maven dependency requires a comment in `pom.xml` explaining why
- Check if an existing library already covers the need before adding

## Git hygiene
- PR description explains *why*, not just *what*
- No commented-out code — delete it (git history preserves it)
- No TODO comments without a linked issue number