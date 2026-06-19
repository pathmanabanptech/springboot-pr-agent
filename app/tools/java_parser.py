import re

_ANNOTATIONS = [
    "@Autowired",
    "@Transactional",
    "@Entity",
    "@RestController",
    "@Controller",
    "@Service",
    "@Repository",
    "@Component",
    "@SpringBootTest",
    "@MockBean",
    "@Mock",
    "@OneToMany",
    "@ManyToMany",
    "@ManyToOne",
    "@OneToOne",
    "@PreAuthorize",
    "@Secured",
    "@RolesAllowed",
]

_FILE_HEADER = re.compile(r"^--- (.+)$", re.MULTILINE)


def extract_signals(diff_text: str) -> dict[str, str]:
    """Return {filename: comma-separated signal list} for each file in the diff."""
    if not diff_text:
        return {}

    # Split diff into per-file blocks
    blocks: dict[str, str] = {}
    current_file = "_unknown_"
    current_lines: list[str] = []

    for line in diff_text.splitlines():
        m = _FILE_HEADER.match(line)
        if m:
            if current_lines:
                blocks[current_file] = "\n".join(current_lines)
            current_file = m.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        blocks[current_file] = "\n".join(current_lines)

    result: dict[str, str] = {}
    for filename, block in blocks.items():
        found = [ann for ann in _ANNOTATIONS if ann in block]
        if found:
            result[filename] = "signals: " + ", ".join(found)

    return result
