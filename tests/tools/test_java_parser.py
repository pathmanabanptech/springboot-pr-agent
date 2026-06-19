from app.tools.java_parser import extract_signals


SAMPLE_DIFF = """\
--- src/main/java/com/example/UserService.java
+@Service
+public class UserService {
+    @Autowired
+    private UserRepository repo;
+
+    @Transactional
+    public void save(User u) { repo.save(u); }
+}

--- src/main/java/com/example/UserController.java
+@RestController
+public class UserController {
+    public List<User> list() { return new ArrayList<>(); }
+}
"""

EMPTY_DIFF = ""


def test_extract_signals_finds_service_annotations():
    result = extract_signals(SAMPLE_DIFF)
    assert "src/main/java/com/example/UserService.java" in result
    signals = result["src/main/java/com/example/UserService.java"]
    assert "@Service" in signals
    assert "@Autowired" in signals
    assert "@Transactional" in signals


def test_extract_signals_finds_controller_annotations():
    result = extract_signals(SAMPLE_DIFF)
    assert "src/main/java/com/example/UserController.java" in result
    signals = result["src/main/java/com/example/UserController.java"]
    assert "@RestController" in signals


def test_extract_signals_empty_diff():
    assert extract_signals(EMPTY_DIFF) == {}


def test_extract_signals_no_annotations():
    diff = "--- src/main/java/Plain.java\n+public class Plain {\n+    void foo() {}\n+}\n"
    result = extract_signals(diff)
    # file appears only if signals found — no annotations means not in result
    assert "src/main/java/Plain.java" not in result


def test_extract_signals_jpa_annotations():
    diff = """\
--- src/main/java/Order.java
+@Entity
+public class Order {
+    @OneToMany
+    private List<Item> items;
+    @ManyToOne
+    private Customer customer;
+}
"""
    result = extract_signals(diff)
    assert "src/main/java/Order.java" in result
    signals = result["src/main/java/Order.java"]
    assert "@Entity" in signals
    assert "@OneToMany" in signals
    assert "@ManyToOne" in signals


def test_extract_signals_security_annotations():
    diff = """\
--- src/main/java/SecureController.java
+@RestController
+public class SecureController {
+    @PreAuthorize("hasRole('ADMIN')")
+    public String admin() { return "ok"; }
+}
"""
    result = extract_signals(diff)
    signals = result["src/main/java/SecureController.java"]
    assert "@PreAuthorize" in signals


def test_extract_signals_test_annotations():
    diff = """\
--- src/test/java/UserServiceTest.java
+@SpringBootTest
+public class UserServiceTest {
+    @MockBean
+    private UserRepository repo;
+}
"""
    result = extract_signals(diff)
    signals = result["src/test/java/UserServiceTest.java"]
    assert "@SpringBootTest" in signals
    assert "@MockBean" in signals
