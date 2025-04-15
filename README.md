# GitHub Contributing Developer Counter

This script processes a list of GitHub repositories, fetches contributor information for each, and generates a detailed CSV file of contributors along with a summary of unique contributors per repository.

## Syntax and Arguments

Execute the script using the following command line:

```bash
python github_contributor_count.py REPO_FILE [OPTIONS]
```

### Required Arguments

- `REPO_FILE`: Path to a text file containing repository names (one per line) in the format owner/repo.

### Optional Arguments

- `--days`: Number of days to look back for contributions (default: 90).
- `--token`: GitHub Personal Access Token (default: none, must be provided if not set in the script).
- `--api_url`: GitHub API base URL (default: https://api.github.com).
- `--output`: Path to save the CSV output file (default: contributors.csv).
- `--debug`: Enable debug output (default: off). Note that all activities are automatically logged.

## License

MIT License

Copyright (c) 2024

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
