# Git Rebase Guide: Rebasing Your Branch on Top of Main

## Overview

When working on a feature branch, the main branch may receive new changes from merged pull requests. To keep your branch up-to-date and avoid merge conflicts later, you can rebase your branch on top of the latest main branch.

## What is Rebasing?

Rebasing takes your branch's commits and replays them on top of another branch (usually main). This creates a linear history and makes your pull request easier to review and merge.

**Before rebase:**
```
main:     A---B---C---D
                   \
your-branch:        E---F
```

**After rebase:**
```
main:     A---B---C---D
                       \
your-branch:            E'---F'
```

## Prerequisites

Before rebasing, ensure you have:
1. Committed all your local changes
2. No uncommitted files in your working directory

Check your status with:
```bash
git status
```

If you have uncommitted changes, either commit them or stash them:
```bash
git stash
```

## Step-by-Step Rebase Instructions

### Step 1: Fetch the Latest Changes from Remote

```bash
git fetch origin
```

This downloads the latest commits from the remote repository without modifying your local branches.

### Step 2: Ensure You're on Your Feature Branch

```bash
git checkout your-branch-name
```

Replace `your-branch-name` with the actual name of your branch.

### Step 3: Rebase onto Main

```bash
git rebase origin/main
```

This command replays your commits on top of the latest main branch.

### Alternative: Interactive Rebase

For more control over the rebase process, use interactive rebase:

```bash
git rebase -i origin/main
```

This opens an editor where you can:
- Reorder commits
- Squash multiple commits into one
- Edit commit messages
- Drop commits you don't want

## Handling Merge Conflicts

If you encounter conflicts during rebase, Git will pause and show you the conflicting files.

### Step 1: View Conflicted Files

```bash
git status
```

Files with conflicts will be listed under "Unmerged paths".

### Step 2: Resolve Conflicts

Open each conflicted file and look for conflict markers:

```
<<<<<<< HEAD
Code from main branch
=======
Your code
>>>>>>> your-commit-message
```

Edit the file to keep the correct code, removing the conflict markers.

### Step 3: Mark Conflicts as Resolved

After fixing conflicts in a file:

```bash
git add <filename>
```

### Step 4: Continue the Rebase

```bash
git rebase --continue
```

Repeat steps 1-4 for each conflicted commit.

### Aborting a Rebase

If you want to cancel the rebase and return to the original state:

```bash
git rebase --abort
```

## Pushing Your Rebased Branch

After a successful rebase, your branch's history has changed. You'll need to force push:

```bash
git push --force-with-lease origin your-branch-name
```

**Important:** Use `--force-with-lease` instead of `--force` to protect against accidentally overwriting others' work.

## Complete Example Workflow

Here's a complete example of rebasing the current branch onto main:

```bash
# 1. Ensure you're on your branch
git checkout copilot/rebase-on-new-main-changes

# 2. Commit any uncommitted changes
git status
# (commit or stash if needed)

# 3. Fetch latest changes
git fetch origin

# 4. Rebase onto main
git rebase origin/main

# 5. If there are conflicts, resolve them:
#    - Edit conflicted files
#    - git add <resolved-files>
#    - git rebase --continue
#    Repeat until rebase is complete

# 6. Push the rebased branch
git push --force-with-lease origin copilot/rebase-on-new-main-changes
```

## Best Practices

1. **Rebase frequently**: Rebase regularly to minimize conflicts
2. **Don't rebase public branches**: Only rebase branches you're working on alone
3. **Communicate with your team**: If others are working on the same branch, coordinate before rebasing
4. **Test after rebasing**: Ensure your code still works after the rebase
5. **Use `--force-with-lease`**: This is safer than `--force` as it checks if the remote branch has changed

## Troubleshooting

### Issue: "Cannot rebase: You have unstaged changes"

**Solution:** Commit or stash your changes first:
```bash
git stash
git rebase origin/main
git stash pop
```

### Issue: "fatal: refusing to merge unrelated histories"

**Solution:** This usually means the branches have no common ancestor. You may need to use:
```bash
git rebase --allow-unrelated-histories origin/main
```

### Issue: Many conflicts during rebase

**Solution:** Consider using merge instead of rebase for this update:
```bash
git rebase --abort
git merge origin/main
```

### Issue: Accidentally rebased and pushed the wrong thing

**Solution:** If you caught it quickly and no one else has pulled:
1. Find the commit before the rebase using `git reflog`
2. Reset to that commit: `git reset --hard <commit-sha>`
3. Push with force: `git push --force-with-lease origin your-branch-name`

## When to Use Merge Instead of Rebase

Consider using `git merge origin/main` instead of rebase if:
- Multiple people are working on the same branch
- You want to preserve the exact history of how changes were made
- The branch has already been published and others may have based work on it

## Additional Resources

- [Git Documentation - Rebasing](https://git-scm.com/book/en/v2/Git-Branching-Rebasing)
- [Atlassian Git Tutorial - Merging vs. Rebasing](https://www.atlassian.com/git/tutorials/merging-vs-rebasing)

## Summary

Rebasing keeps your feature branch up-to-date with the main branch by replaying your commits on top of the latest changes. While it creates a cleaner history, it requires careful handling of conflicts and force-pushing. Follow the steps above, and don't hesitate to ask for help if you run into issues!
