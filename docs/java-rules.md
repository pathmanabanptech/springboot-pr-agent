# Java / SpringBoot Rules Reference

Source of truth for agent system prompts.
When adding or changing a rule: update this file AND the relevant agent's SYSTEM_PROMPT constant.

---

## Code quality rules → code_agent

### Dependency injection
- RULE: no-field-injection
  Detect: @Autowired on private/protected fields
  Message: Use constructor injection. Field injection hides dependencies and breaks testability.
  Severity: high

### Transaction boundaries
- RULE: transaction-on-service-only
  Detect: @Transactional on @Controller, @RestController, or @Repository class
  Message: @Transactional belongs on the service layer only. Controllers should not manage transactions.
  Severity: high

- RULE: transaction-readonly-for-reads
  Detect: public methods named get*/find*/list*/fetch* in @Service without @Transactional(readOnly=true)
  Message: Read-only queries should declare readOnly=true — enables database optimisations.
  Severity: suggestion

### JPA / database
- RULE: no-n-plus-one
  Detect: @OneToMany or @ManyToMany without explicit FetchType.LAZY + @EntityGraph or JOIN FETCH
  Message: Default EAGER fetching on collection relationships causes N+1 queries.
  Severity: high

- RULE: no-jpql-string-concat
  Detect: createQuery() or createNativeQuery() with + string concatenation from method parameters
  Message: Use named parameters (:param) or @Query with parameters to prevent SQL injection.
  Severity: critical

- RULE: no-entity-in-api
  Detect: @RestController method with return type that is a @Entity class
  Message: Never expose JPA entities directly via REST. Return DTOs.
  Severity: high

### Error handling
- RULE: no-swallowed-exception
  Detect: catch block with empty body or only a comment
  Message: Swallowed exception silently hides bugs in production. Log or rethrow.
  Severity: high

- RULE: no-try-catch-in-controller
  Detect: try-catch blocks inside @RestController or @Controller methods
  Message: Use @RestControllerAdvice for centralised, consistent exception handling.
  Severity: medium

### Code hygiene
- RULE: no-system-out
  Detect: System.out.println or System.err.println
  Message: Use SLF4J logger (@Slf4j). System.out doesn't log level, thread, or timestamp.
  Severity: medium

- RULE: no-raw-types
  Detect: List, Map, Set, Collection used without generic type parameters
  Severity: medium

- RULE: no-magic-numbers
  Detect: numeric literals in business logic (excluding 0, 1, -1, 100)
  Message: Extract to a named constant for readability and maintainability.
  Severity: suggestion

### Naming conventions
- RULE: service-suffix
  Detect: @Service class whose name does not end with Service
  Severity: low

- RULE: repository-suffix
  Detect: interface extending JpaRepository/CrudRepository not ending with Repository
  Severity: low

- RULE: dto-no-entity-exposure
  Detect: class ending in DTO that has a field of a @Entity type
  Message: DTOs must not contain JPA entity references.
  Severity: medium

---

## Security rules → security_agent

### Secrets and credentials
- RULE: hardcoded-credential
  Detect: field named password/secret/apikey/token/passwd assigned a string literal
  Message: Hardcoded credentials will be exposed if the repo is ever public.
  Severity: critical

- RULE: no-hardcoded-url
  Detect: String literal containing http:// or https:// in non-test Java source
  Message: Externalise URLs to application.properties or environment variables.
  Severity: high

### Spring Security
- RULE: csrf-disabled
  Detect: .csrf().disable() or csrf(AbstractHttpConfigurer::disable)
  Message: CSRF disabled. Only correct for fully stateless JWT APIs. Document reason.
  Severity: high

- RULE: permit-all-undocumented
  Detect: .permitAll() without a comment on the same or adjacent line
  Message: Document why this endpoint is publicly accessible.
  Severity: medium

- RULE: missing-preauthorize
  Detect: public method in @RestController without @PreAuthorize, @Secured, or @RolesAllowed
  Condition: only flag when spring-security is on the classpath (check pom.xml in diff)
  Severity: medium

### Injection vulnerabilities
- RULE: jpql-injection
  Detect: EntityManager.createQuery() or createNativeQuery() with string concatenation
  Severity: critical

- RULE: path-traversal
  Detect: new File() or Paths.get() or FileInputStream() constructed from request parameter
  Severity: critical

- RULE: spel-injection
  Detect: SpelExpressionParser used with user-supplied input
  Severity: critical

### Data exposure
- RULE: sensitive-data-in-log
  Detect: log.info/debug/error/warn statement referencing variable named password/token/card/ssn/secret
  Message: Logging sensitive fields creates compliance violations and security risk.
  Severity: high

---

## Test rules → test_agent

- RULE: missing-test
  Detect: new public class annotated @Service or @Component with no corresponding test file in this PR
  Message: New service logic should have unit tests in the same PR.
  Severity: medium

- RULE: empty-test-body
  Detect: @Test method with empty method body
  Message: Empty test always passes and provides zero coverage value.
  Severity: high

- RULE: no-assertion
  Detect: @Test method with no call to assert*/verify*/assertEquals/assertThat/assertTrue/assertFalse
  Message: Test calls code but makes no assertion — it will never catch a regression.
  Severity: high

- RULE: springboottest-overuse
  Detect: @SpringBootTest on a test class that does not inject a real @Autowired service or web layer
  Message: Use @ExtendWith(MockitoExtension.class) for pure unit tests. @SpringBootTest is 10–100× slower.
  Severity: medium

- RULE: mockbean-wrong-context
  Detect: @MockBean used in a test class without @SpringBootTest or @WebMvcTest
  Message: @MockBean only works in Spring test context. Use @Mock with Mockito for unit tests.
  Severity: medium

- RULE: missing-failure-test
  Detect: new @Service method with only a happy-path test and no test for exception/failure case
  Severity: low