# CodePrinter

**CodePrinter** is designed as a simple local tool for selecting, packaging, and formatting code files to share with Large Language Models (LLMs).


## Quick Start

To run CodePrinter:
1. Clone this repository:
   ```bash
   git clone https://github.com/ChristianCasazza/codeprinter
   ```
2. Start the application using `uv`:
   ```bash
   uv run app.py
   ```

Thanks to `uv`, no virtual environment (venv) setup is required because the package dependencies are already included within the script.

### Installing `uv`
If you don't already have `uv` installed, you can add it via pip:
```bash
pip install uv
```
For more details, refer to the [uv documentation](https://docs.astral.sh/uv/getting-started/installation/).

## Using CodePrinter

1. **Enter a Repository Source**
   - For GitHub: Enter a repository URL (e.g., https://github.com/username/repo)
   - For local: Enter a directory path (e.g., /path/to/your/project)

2. **Select Files**
   - Use the directory tree to check specific files
   - Use extension filters to select files by type
   - Search for specific files

3. **Generate Output**
   - Click "Selected Files" for only checked files
   - Click "Full Project" for all files with selected ones highlighted

4. **Use the Output**
   - Copy to clipboard
   - Download as a file
   - Toggle syntax highlighting for better readability

## Keyboard Shortcuts

- `Ctrl + F`: Focus search box
- `Ctrl + E`: Expand all folders
- `Ctrl + C`: Collapse all folders
- `Ctrl + G`: Generate selected files
- `Ctrl + Shift + G`: Generate full project
- `Escape`: Close modals/fullscreen

## Configuration

### Excluding Folders
Within the `app.py`, you'll find the `skip_dirs` variable, which lists directories to exclude from the UI. By default, it includes:
- `.venv`
- `node_modules`
- `.git`
- `.vscode`
- `.evidence`
- `target`

Edit this list as needed to customize which folders are skipped.

### Managing File Formats
CodePrinter now includes a dynamic file format management system:

1. Click the "Manage" button next to the file extension filters
2. Add, edit, or delete file formats through the Format Manager
3. Customize:
   - File extensions (e.g., `.js`, `.py`)
   - Display colors
   - Syntax highlighting language
   - Enable/disable specific formats

Changes take effect immediately without editing code. The formats are stored in the database for persistence between sessions.

### Working with GitHub
Passing public GitHub repo links works in GitHub mode the same way as local mode.

However, especially large repos might be rate limited by GitHub and fail. This can be mitigated by providing a GitHub access token.

GitHub mode also works with your own personal private repos. Create a GitHub Personal Access Token (PAT) with the repo permissions to access private repositories.

#### GitHub Token

For private GitHub repositories, you'll need a personal access token:

1. Go to [GitHub Token Settings](https://github.com/settings/tokens)
2. Generate a new token with the "repo" scope
3. Enter the token in the application
4. Alternatively, set it as the `GITHUB_TOKEN` environment variable

## Contributing

Feel free to submit issues or feature requests via the GitHub repository.

Best place to contact me is sending me a DM on X at [@CasazzaNY](https://x.com/CasazzaNY)

## Acknowledgements

This was made possible thanks to Abin Thomas open-sourcing [repo2txt](https://github.com/abinthomasonline/repo2txt) as a base to build on, so I am open-sourcing this to pass it forward. Thank you, Abin! My main change was converting the app to be a uv flask executable app, and making local mode work by just passing a local path instead of a zip file.

---
**Happy coding!**