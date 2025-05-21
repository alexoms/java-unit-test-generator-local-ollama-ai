Here’s a `README.md` you can use to describe your `generate_junit_tests.py` tool:

---

````markdown
# 🧪 Java → JUnit Test Generator using Ollama

This script reads `.java` source files from a given directory, breaks them down **method by method**, and uses a local **Ollama LLM** (like `codellama` or `qwen3`) to generate corresponding **JUnit 5 test cases** with a goal of at least **80% code coverage**.

Tests are streamed from the model and saved as individual `.md` files per method for easy review or manual copying into test suites.

---

## 📦 Features

- ✅ CLI tool, pure Python (no `requests` dependency)
- ✅ Splits large Java files by method to stay within token limits
- ✅ Reinforces prompt goal per chunk to avoid LLM derailment
- ✅ Saves output as Markdown for each method
- ✅ Uses Ollama's `/api/generate` with streaming response

---

## 🛠 Requirements

- Python 3.10+
- [Ollama](https://ollama.com) installed and running locally
- A model like `codellama` or `qwen3` pulled:
  ```bash
  ollama pull codellama
````

---

## 🚀 Usage

```bash
python3 generate_junit_tests.py /path/to/java/files
```

### Example:

```bash
python3 generate_junit_tests.py ./src/main/java
```

The script will:

1. Read all `.java` files in the directory (recursively),
2. Extract each method individually,
3. Prompt the LLM with:

   > Generate a JUnit 5 test for this method...
4. Save the results as:

```
tests_markdown/
├── MyClass_Method1_Test.md
├── MyClass_Method2_Test.md
```

---

## ⚙️ Configuration

You can adjust:

| Parameter    | Location         | Description                                          |
| ------------ | ---------------- | ---------------------------------------------------- |
| `MODEL`      | in script header | The Ollama model to use (`codellama`, `qwen3`, etc.) |
| `OUTPUT_DIR` | in script header | Where Markdown results are stored                    |

---

## 📌 Notes

* The method extraction uses a basic regex. For more advanced Java code, a parser like [JavaParser](https://javaparser.org/) may improve accuracy.
* Prompts are crafted to focus on **unit test generation** and avoid explanation mode in LLMs.
* Output is Markdown for easy reading, but can be adapted to `.java` file generation.

---

## 🧠 Sample Prompt Sent to Ollama

````text
You are a Java testing expert.

Generate a JUnit 5 test for the following method from class `MyService`.
Ensure good naming and cover edge cases. Use mocks if needed.

```java
public int add(int a, int b) {
    return a + b;
}
````

Reminder: Write the JUnit 5 test code (with imports) for the method above.

```

---

## 🧼 License

MIT License – Use freely, modify, contribute!

---

## ✨ Author

Unidatum Integrated Products LLC
```

---
