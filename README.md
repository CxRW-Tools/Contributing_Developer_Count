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
- `--debug`: Enable debug output (default: off).
