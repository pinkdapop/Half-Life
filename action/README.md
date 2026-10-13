# halflife as a GitHub Action

Add this workflow to a repo and halflife comments on pull requests that touch your docs.

```yaml
name: halflife
on:
  pull_request:
    paths: ["**/*.md"]
jobs:
  check:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: YOUR_USER/halflife/action@main
        with:
          files: README.md docs/install.md
          nebius_api_key: ${{ secrets.NEBIUS_API_KEY }}
          tavily_api_key: ${{ secrets.TAVILY_API_KEY }}
          max_claims: 60
```

Each file gets a table: rotted claims first, what is true now, and the source that settles it.
Cap `max_claims` to keep Tavily usage predictable on busy repos.
