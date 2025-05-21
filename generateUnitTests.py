import os
import re
import sys
import http.client
import json

OLLAMA_HOST = "localhost"
OLLAMA_PORT = 11434
MODEL = "llama3.2:lateest"
OUTPUT_DIR = "tests_markdown"

# Matches method definitions (very basic Java regex)
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

def write_markdown(output_text, class_filename, method_index):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    base = os.path.splitext(os.path.basename(class_filename))[0]
    out_file = os.path.join(OUTPUT_DIR, f"{base}_Method{method_index}_Test.md")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"# JUnit Test for Method {method_index} in `{class_filename}`\n\n")
        f.write("```\n")
        f.write(output_text)
        f.write("\n```\n")
    print(f"\n✅ Saved test to: {out_file}")

def process_file(filepath):
    print(f"\n=== Processing: {filepath} ===")
    java_code = read_file(filepath)
    methods = extract_methods(java_code)
    class_name = os.path.splitext(os.path.basename(filepath))[0]

    if not methods:
        print("⚠️ No methods detected.")
        return

    for idx, method_code in enumerate(methods, start=1):
        print(f"\n--- Generating test for method {idx} ---")
        prompt = build_prompt(method_code, class_name, idx)
        output = send_to_ollama(prompt)
        write_markdown(output, filepath, method_index=idx)

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 generate_junit_tests.py <path_to_java_source_folder>")
        sys.exit(1)

    java_root = sys.argv[1]
    if not os.path.isdir(java_root):
        print(f"Error: '{java_root}' is not a valid directory.")
        sys.exit(1)

    java_files = collect_java_files(java_root)
    if not java_files:
        print(f"No .java files found in {java_root}")
        return

    for file in java_files:
        process_file(file)

if __name__ == "__main__":
    main()
