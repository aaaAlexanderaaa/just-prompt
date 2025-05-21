Feature Request: Prompt from File to File with Context Files

## Implementation Notes

- Create a new tool 'prompt_from_file_to_file_w_context' in src/just_prompt/molecules/prompt_from_file_to_file_w_context.py
- Definition: prompt_from_file_to_file_w_context(from_file: str, context_files: List[str], models_prefixed_by_provider: List[str] = None, output_dir: str = ".") -> None:
- This tool extends the existing prompt_from_file_to_file functionality by injecting context files into the prompt before sending to LLMs
- The tool will read the from_file and search for the placeholder `{{context_files}}`
- If `{{context_files}}` is not found in the from_file, throw an error requiring this placeholder to be present
- Replace `{{context_files}}` with an XML block containing all context files:
  ```xml
  <context_files>
      <file name="absolute/path/to/file1.py">
          ... file1 content ...
      </file>
      <file name="absolute/path/to/file2.md"> 
          ... file2 content ...
      </file>
      ... repeat for all context_files ...
  </context_files>
  ```
- Read each file in context_files (using absolute paths) and inject their contents into the XML structure
- After context injection, use the existing prompt_from_file_to_file logic to send the enhanced prompt to all specified models
- Each context file should be wrapped in a `<file name="...">content</file>` tag within the `<context_files>` block
- Handle file reading errors gracefully with descriptive error messages
- Validate that all context_files exist and are readable before processing
- The enhanced prompt (with context files injected) should be sent to all models specified in models_prefixed_by_provider
- Output files follow the same naming convention as prompt_from_file_to_file: `{output_dir}/{sanitized_filename}_{provider}_{model}.md`

## Relevant Files
- src/just_prompt/server.py (add new MCP tool endpoint)
- src/just_prompt/molecules/prompt_from_file_to_file_w_context.py (new file)
- src/just_prompt/molecules/prompt_from_file_to_file.py (reference existing logic)
- src/just_prompt/atoms/shared/utils.py (for file operations and validation)
- src/just_prompt/atoms/shared/validator.py (for input validation)
- src/just_prompt/tests/molecules/test_prompt_from_file_to_file_w_context.py (new test file)

## Validation (Close the Loop)
> Be sure to test this new capability with uv run pytest.

- Create comprehensive tests in test_prompt_from_file_to_file_w_context.py covering:
  - Normal operation with valid context files
  - Error when {{context_files}} placeholder is missing
  - Error when context files don't exist or aren't readable
  - Proper XML formatting of context files
  - Integration with existing prompt_from_file_to_file workflow
- `uv run pytest src/just_prompt/tests/molecules/test_prompt_from_file_to_file_w_context.py`
- `uv run just-prompt --help` to validate the tool works as expected
- Test end-to-end functionality by creating a sample prompt file with {{context_files}} placeholder and sample context files
- After implementation, update README.md with the new tool's functionality and parameters
- Run `git ls-files` to update the directory tree in the README with the new files

## Error Handling Requirements
- Validate that from_file exists and is readable
- Validate that all files in context_files list exist and are readable  
- Require {{context_files}} placeholder to be present in from_file content
- Provide clear error messages for missing files, permission issues, or missing placeholder
- Handle large context files gracefully (consider file size limits if needed)

## Example Usage
```python
# Prompt file content (example.txt):
"""
Please analyze the following codebase files:

{{context_files}}

Based on the code above, suggest improvements for better performance.
"""

# Tool call:
prompt_from_file_to_file_w_context(
    from_file="prompts/example.txt",
    context_files=[
        "/absolute/path/to/src/main.py",
        "/absolute/path/to/src/utils.py", 
        "/absolute/path/to/README.md"
    ],
    models_prefixed_by_provider=["openai:gpt-4o", "anthropic:claude-3-5-sonnet"],
    output_dir="analysis_results"
)
```