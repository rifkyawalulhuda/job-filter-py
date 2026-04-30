cat > AGENTS.md <<'EOF'
# Project agent rules

Mandatory: use RTK for shell-heavy work.

Always prefer:
- rtk git status
- rtk git diff
- rtk rg
- rtk grep
- rtk find
- rtk ls
- rtk npm test / rtk pnpm test / rtk pytest

Do not use raw git diff, raw rg, raw grep, or raw test commands unless RTK fails.
EOF