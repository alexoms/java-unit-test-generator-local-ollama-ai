import os
import re
import sys
import http.client
import json

OLLAMA_HOST = "localhost"
OLLAMA_PORT = 11434
MODEL = "llama3.2:latest"
OUTPUT_DIR = "tests_markdown"
SKIPPED_LOG = os.path.join(OUTPUT_DIR, "_skipped_pojos.log")

METHOD_REGEX = re.compile(
    r'''^[ \t]*          # leading space
    (?:@\w+(?:\([^\)]*\))?\s*)*  # optional annotations like @Override
    (?:public|protected|private|static|final|native|synchronized|abstract|transient|strictfp|\s)+
    [\w<>\[\],\s]+        # return type (e.g., List<String>)
    \s+
    (\w+)                # method name
    \s*\([^)]*\)         # params (...)
    \s*(?:throws\s+[^{]+)?  # optional throws clause
    \s*(?=\{)            # must be followed by a {
    ''',
    re.MULTILINE | re.VERBOSE
)

def collect_java_files(root_dir):
    java_files = []
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".java"):
                java_files.append(os.path.join(root, file))
    return java_files

def read_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

def extract_methods(java_code):
    lines = java_code.splitlines()
    methods = []
    current = []
    brace_count = 0
    in_method = False

    for line in lines:
        if METHOD_REGEX.match(line.strip()) and not in_method:
            if current:
                methods.append("\n".join(current))
                current = []
            in_method = True
            brace_count = 0

        if in_method:
            current.append(line)
            brace_count += line.count("{") - line.count("}")
            if brace_count == 0 and current:
                methods.append("\n".join(current))
                current = []
                in_method = False

    if current:
        methods.append("\n".join(current))
    return methods

def is_trivial_method(method_code):
    lines = [line.strip() for line in method_code.strip().splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    first_line = lines[0].lower()
    if any(k in first_line for k in ['get', 'set', 'is']):
        if len(lines) <= 4:
            body = " ".join(lines[1:])
            return (
                body.startswith("return ") or
                ("=" in body and ("this." in body or body.endswith(";")))
            )
    return False

def build_prompt(method_code, class_name, method_index):
    return (
        f"You are a Java testing expert.\n\n"
        f"Generate a JUnit 5 test for the following method from class `{class_name}`. "
        f"Ensure good naming and cover edge cases. Use mocks if needed.\n\n"
        f"```java\n{method_code}\n```\n\n"
        f"Reminder: Write the JUnit 5 test code (with imports) for the method above."
    )

def send_to_ollama(prompt):
    conn = http.client.HTTPConnection(OLLAMA_HOST, OLLAMA_PORT)
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": True
    }

    conn.request("POST", "/api/generate", body=json.dumps(payload), headers=headers)
    response = conn.getresponse()

    output = ""
    while True:
        line = response.readline()
        if not line:
            break
        try:
            data = json.loads(line.decode("utf-8"))
            chunk = data.get("response", "")
            output += chunk
            print(chunk, end="", flush=True)
        except json.JSONDecodeError:
            continue

    conn.close()
    return output

def write_markdown(output_text, full_file_path, java_root, method_index):
    rel_path = os.path.relpath(full_file_path, java_root)
    rel_dir = os.path.dirname(rel_path)
    base_name = os.path.splitext(os.path.basename(full_file_path))[0]

    output_subdir = os.path.join(OUTPUT_DIR, rel_dir)
    os.makedirs(output_subdir, exist_ok=True)

    out_file_path = os.path.join(output_subdir, f"{base_name}_Method{method_index}_Test.md")
    with open(out_file_path, "w", encoding="utf-8") as f:
        f.write(f"# JUnit Test for Method {method_index} in `{base_name}.java`\n\n")
        f.write("```\n")
        f.write(output_text)
        f.write("\n```\n")
    print(f"\n✅ Saved test to: {out_file_path}")

def log_skipped_pojo(class_name, file_path, method_count, trivial_count):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(SKIPPED_LOG, "a", encoding="utf-8") as f:
        f.write(f"{class_name} - {file_path} (skipped {trivial_count}/{method_count} trivial methods)\n")

def process_file(filepath, java_root):
    print(f"\n=== Processing: {filepath} ===")
    java_code = read_file(filepath)
    methods = extract_methods(java_code)
    class_name = os.path.splitext(os.path.basename(filepath))[0]

    if not methods:
        print("⚠️ No methods detected.")
        return

    trivial_count = sum(1 for m in methods if is_trivial_method(m))
    total_methods = len(methods)
    trivial_ratio = trivial_count / total_methods

    # Large POJO: skip entirely
    if trivial_ratio >= 0.8 and total_methods > 60:
        print(f"⚠️ Skipping large POJO: {class_name} ({trivial_count}/{total_methods} trivial)")
        log_skipped_pojo(class_name, filepath, total_methods, trivial_count)
        return

    # Small POJO: generate one test for the full class
    if trivial_ratio >= 0.8:
        print(f"ℹ️ Detected small POJO: {class_name} ({trivial_count}/{total_methods} trivial)")
        prompt = (
            f"This is a simple Java POJO named `{class_name}`. "
            f"Please generate a single JUnit 5 test class that instantiates it, sets values, "
            f"and verifies behavior via getters and equals/hashCode if present.\n\n"
            f"```java\n{java_code}\n```"
        )
        output = send_to_ollama(prompt)
        write_markdown(output, filepath, java_root, method_index="All")
        return

    # Mixed-content class: generate one per non-trivial method
    for idx, method_code in enumerate(methods, start=1):
        if is_trivial_method(method_code):
            print(f"🔸 Skipping trivial method {idx} in {class_name}")
            continue

        print(f"\n--- Generating test for method {idx} ---")
        prompt = build_prompt(method_code, class_name, idx)
        output = send_to_ollama(prompt)
        write_markdown(output, filepath, java_root, method_index=idx)

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 generate_junit_tests.py <path_to_java_source_folder>")
        sys.exit(1)

    java_root = os.path.abspath(sys.argv[1])
    if not os.path.isdir(java_root):
        print(f"Error: '{java_root}' is not a valid directory.")
        sys.exit(1)

    if os.path.exists(SKIPPED_LOG):
        os.remove(SKIPPED_LOG)

    java_files = collect_java_files(java_root)
    if not java_files:
        print(f"No .java files found in {java_root}")
        return

    for file in java_files:
        process_file(file, java_root)

if __name__ == "__main__":
    main()
