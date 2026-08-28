from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT=Path(__file__).resolve().parents[3]
PUBLISHER=REPO_ROOT/"automation/wp3_r/publish_current_safely.sh"


def git(cwd: Path,*args: str) -> str:
    cp=subprocess.run(["git",*args],cwd=cwd,text=True,capture_output=True,check=True)
    return cp.stdout.strip()


def test_shared_rolling_branch_preserves_other_workflow_state(tmp_path: Path) -> None:
    remote=tmp_path/"remote.git"
    work=tmp_path/"work"
    subprocess.run(["git","init","--bare",str(remote)],check=True,capture_output=True)
    subprocess.run(["git","clone",str(remote),str(work)],check=True,capture_output=True)
    git(work,"config","user.name","test")
    git(work,"config","user.email","test@example.com")

    (work/"weekly.txt").write_text("weekly-main\n",encoding="utf-8")
    (work/"daily.txt").write_text("daily-main\n",encoding="utf-8")
    git(work,"add",".")
    git(work,"commit","-m","main")
    git(work,"branch","-M","main")
    git(work,"push","-u","origin","main")

    git(work,"checkout","-b","automation/wp3-r-candidate-current")
    (work/"weekly.txt").write_text("weekly-fresh\n",encoding="utf-8")
    git(work,"add","weekly.txt")
    git(work,"commit","-m","weekly publish")
    git(work,"push","-u","origin","automation/wp3-r-candidate-current")

    git(work,"checkout","main")
    (work/"daily.txt").write_text("daily-fresh\n",encoding="utf-8")
    subprocess.run(
        ["bash",str(PUBLISHER),"daily publish","daily.txt"],
        cwd=work,text=True,capture_output=True,check=True,
        env={
            **__import__("os").environ,
            "WP3R_BASE_BRANCH":"main",
            "WP3R_PUBLISH_BRANCH":"automation/wp3-r-candidate-current",
        },
    )

    assert (work/"weekly.txt").read_text(encoding="utf-8")=="weekly-fresh\n"
    assert (work/"daily.txt").read_text(encoding="utf-8")=="daily-fresh\n"
    git(work,"fetch","origin","automation/wp3-r-candidate-current")
    assert git(work,"show","FETCH_HEAD:weekly.txt")=="weekly-fresh"
    assert git(work,"show","FETCH_HEAD:daily.txt")=="daily-fresh"
