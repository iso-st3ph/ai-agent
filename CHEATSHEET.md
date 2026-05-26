# Context-Switching Cheat Sheet

Quick reference for switching between GitHub accounts, Python virtual
environments, and Kubernetes contexts.

---

## GitHub accounts (gh CLI)

```bash
gh auth status                   # list all logged-in accounts; shows which is ACTIVE
gh auth switch --user NAME       # switch active account (e.g. iso-st3ph / sski99er)
gh auth switch                   # interactive picker if you omit --user
gh auth login                    # add a new account
gh auth logout --user NAME       # remove an account
```

Make sure the repo's commit identity matches the active gh account:

```bash
git config user.name             # show this repo's identity
git config user.email
git config user.name  "iso-st3ph"               # set per-repo (no --global)
git config user.email "personal@example.com"
```

Check / change where a repo pushes:

```bash
git remote -v
git remote set-url origin https://github.com/USER/REPO.git
```

---

## Python virtual environments

```bash
python3 -m venv .venv            # create a venv in current folder
source .venv/bin/activate        # ACTIVATE (mac/Linux)
.venv\Scripts\activate           # ACTIVATE (Windows)
deactivate                       # DEACTIVATE (back to system python)
```

Which env am I in?

```bash
which python                     # path -> inside .venv = active
echo $VIRTUAL_ENV                # active venv path, or empty if none
python --version
```

Packages in the active env:

```bash
pip list
pip show PACKAGE
pip freeze > requirements.txt    # save deps
pip install -r requirements.txt  # restore deps
```

> A venv is tied to a FOLDER, not a script. cd into the project + activate
> once; all scripts in that folder share the same env.

---

## Kubernetes contexts (kubectl)

```bash
kubectl config get-contexts      # list all contexts (* marks current)
kubectl config current-context   # show just the active one
kubectl config use-context NAME  # SWITCH active context
kubectl config rename-context OLD NEW
```

Namespaces (set a default for the current context):

```bash
kubectl config set-context --current --namespace=NS
kubectl get namespaces
```

Working with multiple kubeconfig files:

```bash
echo $KUBECONFIG                                    # which config file(s) in use
export KUBECONFIG=~/.kube/config                    # use a specific file
export KUBECONFIG=~/.kube/config:~/.kube/rke2.yaml  # merge multiple (colon-separated)
kubectl config view --flatten > ~/.kube/merged.yaml # merge into one file
```

Per-command override without switching:

```bash
kubectl --context=NAME get pods
kubectl --kubeconfig=/path/to/config get nodes
```

---

## Quick mental model

| Switch        | Controls                          | Command              |
|---------------|-----------------------------------|----------------------|
| gh account    | WHO you are to GitHub             | `gh auth switch`     |
| git config    | WHO commits are attributed to     | per-repo identity    |
| venv          | WHICH python + packages           | `source .../activate`|
| kubectl ctx   | WHICH cluster you target          | `use-context`        |

All four are independent. The classic foot-gun is assuming switching one
switched another — always check the active one before you act.
