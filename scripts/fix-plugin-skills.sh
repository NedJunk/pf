#!/usr/bin/env bash
# Fix all claude-code-skills plugins with "skills": "./" by creating a skills/ subdir with symlinks

set -euo pipefail

CACHE="/Users/dg/.claude/plugins/cache/claude-code-skills"

# Find all plugin.json files with the bad path
while IFS= read -r plugin_json; do
    plugin_root="$(dirname "$(dirname "$plugin_json")")"
    skills_dir="$plugin_root/skills"

    # Skip if already fixed
    if grep -q '"skills": "./skills/"' "$plugin_json"; then
        echo "SKIP (already fixed): $plugin_json"
        continue
    fi

    # Create skills/ dir
    mkdir -p "$skills_dir"

    # Symlink all non-hidden subdirectories (except skills/ itself and .claude-plugin)
    for subdir in "$plugin_root"/*/; do
        name="$(basename "$subdir")"
        [[ "$name" == "skills" ]] && continue
        [[ "$name" == .* ]] && continue
        # Only symlink dirs that look like skill packages (contain SKILL.md or assets/ or references/)
        if [[ -f "$subdir/SKILL.md" ]] || [[ -d "$subdir/assets" ]] || [[ -d "$subdir/references" ]] || [[ -d "$subdir/scripts" ]]; then
            ln -sf "../$name" "$skills_dir/$name" 2>/dev/null || true
        fi
    done

    # If skills/ ended up empty, symlink everything non-hidden
    if [[ -z "$(ls -A "$skills_dir" 2>/dev/null)" ]]; then
        for subdir in "$plugin_root"/*/; do
            name="$(basename "$subdir")"
            [[ "$name" == "skills" ]] && continue
            [[ "$name" == .* ]] && continue
            ln -sf "../$name" "$skills_dir/$name" 2>/dev/null || true
        done
    fi

    # Patch plugin.json
    sed -i '' 's|"skills": "./"$|"skills": "./skills/"|' "$plugin_json"
    echo "FIXED: $plugin_json ($(ls "$skills_dir" | wc -l | tr -d ' ') skills linked)"

done < <(find "$CACHE" -name "plugin.json" | xargs grep -l '"skills": "./"' 2>/dev/null)

echo "Done."
