#!/usr/bin/env python3
"""
Harness Step Executor — phase 내 step을 순차 실행하고 자가 교정한다.
Google AI Studio (Gemini API) 기반.

Usage:
    python3 scripts/execute.py <phase-dir> [--push]
"""

import argparse
import contextlib
import json
import os
import subprocess
import sys
import threading
import time
import types
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

try:
    import google.generativeai as genai
except ImportError:
    print("ERROR: google-generativeai 패키지가 설치되어 있지 않습니다.")
    print("  pip install google-generativeai")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent


@contextlib.contextmanager
def progress_indicator(label: str):
    """터미널 진행 표시기. with 문으로 사용하며 .elapsed 로 경과 시간을 읽는다."""
    frames = "◐◓◑◒"
    stop = threading.Event()
    t0 = time.monotonic()

    def _animate():
        idx = 0
        while not stop.wait(0.12):
            sec = int(time.monotonic() - t0)
            sys.stderr.write(f"\r{frames[idx % len(frames)]} {label} [{sec}s]")
            sys.stderr.flush()
            idx += 1
        sys.stderr.write("\r" + " " * (len(label) + 20) + "\r")
        sys.stderr.flush()

    th = threading.Thread(target=_animate, daemon=True)
    th.start()
    info = types.SimpleNamespace(elapsed=0.0)
    try:
        yield info
    finally:
        stop.set()
        th.join()
        info.elapsed = time.monotonic() - t0


class StepExecutor:
    """Phase 디렉토리 안의 step들을 순차 실행하는 하네스."""

    MAX_RETRIES = 3
    FEAT_MSG = "feat({phase}): step {num} — {name}"
    CHORE_MSG = "chore({phase}): step {num} output"
    TZ = timezone(timedelta(hours=9))

    # Gemini 모델 설정
    GEMINI_MODEL = "gemini-2.5-pro"
    GEMINI_TEMPERATURE = 0.2

    def __init__(self, phase_dir_name: str, *, auto_push: bool = False):
        self._root = str(ROOT)
        self._phases_dir = ROOT / "phases"
        self._phase_dir = self._phases_dir / phase_dir_name
        self._phase_dir_name = phase_dir_name
        self._top_index_file = self._phases_dir / "index.json"
        self._auto_push = auto_push

        if not self._phase_dir.is_dir():
            print(f"ERROR: {self._phase_dir} not found")
            sys.exit(1)

        self._index_file = self._phase_dir / "index.json"
        if not self._index_file.exists():
            print(f"ERROR: {self._index_file} not found")
            sys.exit(1)

        idx = self._read_json(self._index_file)
        self._project = idx.get("project", "project")
        self._phase_name = idx.get("phase", phase_dir_name)
        self._total = len(idx["steps"])

        # Gemini API 초기화
        self._init_gemini()

    def _init_gemini(self):
        """Gemini API 클라이언트 초기화"""
        api_key = os.environ.get("GEMINI_API_KEY", "")

        # backend/.env 에서도 읽기 시도
        if not api_key:
            env_file = ROOT / "backend" / ".env"
            if env_file.exists():
                for line in env_file.read_text().splitlines():
                    if line.startswith("GEMINI_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break

        if not api_key:
            print("ERROR: GEMINI_API_KEY가 설정되어 있지 않습니다.")
            print("  export GEMINI_API_KEY=your-key")
            print("  또는 backend/.env 파일에 GEMINI_API_KEY=your-key 를 추가하세요.")
            sys.exit(1)

        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(
            model_name=self.GEMINI_MODEL,
            generation_config=genai.GenerationConfig(
                temperature=self.GEMINI_TEMPERATURE,
                max_output_tokens=65536,
            ),
        )

    def run(self):
        self._print_header()
        self._check_blockers()
        self._checkout_branch()
        guardrails = self._load_guardrails()
        self._ensure_created_at()
        self._execute_all_steps(guardrails)
        self._finalize()

    # --- timestamps ---

    def _stamp(self) -> str:
        return datetime.now(self.TZ).strftime("%Y-%m-%dT%H:%M:%S%z")

    # --- JSON I/O ---

    @staticmethod
    def _read_json(p: Path) -> dict:
        return json.loads(p.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(p: Path, data: dict):
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- git ---

    def _run_git(self, *args) -> subprocess.CompletedProcess:
        cmd = ["git"] + list(args)
        return subprocess.run(cmd, cwd=self._root, capture_output=True, text=True)

    def _checkout_branch(self):
        branch = f"feat-{self._phase_name}"

        r = self._run_git("rev-parse", "--abbrev-ref", "HEAD")
        if r.returncode != 0:
            print(f"  ERROR: git을 사용할 수 없거나 git repo가 아닙니다.")
            print(f"  {r.stderr.strip()}")
            sys.exit(1)

        if r.stdout.strip() == branch:
            return

        r = self._run_git("rev-parse", "--verify", branch)
        r = self._run_git("checkout", branch) if r.returncode == 0 else self._run_git("checkout", "-b", branch)

        if r.returncode != 0:
            print(f"  ERROR: 브랜치 '{branch}' checkout 실패.")
            print(f"  {r.stderr.strip()}")
            print(f"  Hint: 변경사항을 stash하거나 commit한 후 다시 시도하세요.")
            sys.exit(1)

        print(f"  Branch: {branch}")

    def _commit_step(self, step_num: int, step_name: str):
        output_rel = f"phases/{self._phase_dir_name}/step{step_num}-output.json"
        index_rel = f"phases/{self._phase_dir_name}/index.json"

        self._run_git("add", "-A")
        self._run_git("reset", "HEAD", "--", output_rel)
        self._run_git("reset", "HEAD", "--", index_rel)

        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            msg = self.FEAT_MSG.format(phase=self._phase_name, num=step_num, name=step_name)
            r = self._run_git("commit", "-m", msg)
            if r.returncode == 0:
                print(f"  Commit: {msg}")
            else:
                print(f"  WARN: 코드 커밋 실패: {r.stderr.strip()}")

        self._run_git("add", "-A")
        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            msg = self.CHORE_MSG.format(phase=self._phase_name, num=step_num)
            r = self._run_git("commit", "-m", msg)
            if r.returncode != 0:
                print(f"  WARN: housekeeping 커밋 실패: {r.stderr.strip()}")

    # --- top-level index ---

    def _update_top_index(self, status: str):
        if not self._top_index_file.exists():
            return
        top = self._read_json(self._top_index_file)
        ts = self._stamp()
        for phase in top.get("phases", []):
            if phase.get("dir") == self._phase_dir_name:
                phase["status"] = status
                ts_key = {"completed": "completed_at", "error": "failed_at", "blocked": "blocked_at"}.get(status)
                if ts_key:
                    phase[ts_key] = ts
                break
        self._write_json(self._top_index_file, top)

    # --- guardrails & context ---

    def _load_guardrails(self) -> str:
        sections = []
        gemini_md = ROOT / "GEMINI.md"
        if gemini_md.exists():
            sections.append(f"## 프로젝트 규칙 (GEMINI.md)\n\n{gemini_md.read_text()}")
        docs_dir = ROOT / "docs"
        if docs_dir.is_dir():
            for doc in sorted(docs_dir.glob("*.md")):
                sections.append(f"## {doc.stem}\n\n{doc.read_text()}")
        return "\n\n---\n\n".join(sections) if sections else ""

    @staticmethod
    def _build_step_context(index: dict) -> str:
        lines = [
            f"- Step {s['step']} ({s['name']}): {s['summary']}"
            for s in index["steps"]
            if s["status"] == "completed" and s.get("summary")
        ]
        if not lines:
            return ""
        return "## 이전 Step 산출물\n\n" + "\n".join(lines) + "\n\n"

    def _build_preamble(self, guardrails: str, step_context: str,
                        prev_error: Optional[str] = None) -> str:
        commit_example = self.FEAT_MSG.format(
            phase=self._phase_name, num="N", name="<step-name>"
        )
        retry_section = ""
        if prev_error:
            retry_section = (
                f"\n## ⚠ 이전 시도 실패 — 아래 에러를 반드시 참고하여 수정하라\n\n"
                f"{prev_error}\n\n---\n\n"
            )
        return (
            f"당신은 {self._project} 프로젝트의 개발자입니다. 아래 step을 수행하세요.\n\n"
            f"{guardrails}\n\n---\n\n"
            f"{step_context}{retry_section}"
            f"## 작업 규칙\n\n"
            f"1. 이전 step에서 작성된 코드를 확인하고 일관성을 유지하라.\n"
            f"2. 이 step에 명시된 작업만 수행하라. 추가 기능이나 파일을 만들지 마라.\n"
            f"3. 기존 테스트를 깨뜨리지 마라.\n"
            f"4. AC(Acceptance Criteria) 검증을 직접 실행하라.\n"
            f"5. /phases/{self._phase_dir_name}/index.json의 해당 step status를 업데이트하라:\n"
            f"   - AC 통과 → \"completed\" + \"summary\" 필드에 이 step의 산출물을 한 줄로 요약\n"
            f"   - {self.MAX_RETRIES}회 수정 시도 후에도 실패 → \"error\" + \"error_message\" 기록\n"
            f"   - 사용자 개입이 필요한 경우 (API 키, 인증, 수동 설정 등) → \"blocked\" + \"blocked_reason\" 기록 후 즉시 중단\n"
            f"6. 모든 변경사항을 커밋하라:\n"
            f"   {commit_example}\n\n---\n\n"
        )

    # --- Gemini 호출 ---

    def _collect_project_files(self) -> str:
        """프로젝트의 주요 소스 파일들을 수집하여 컨텍스트로 제공"""
        files_content = []
        root = Path(self._root)

        # 수집할 파일 패턴들
        patterns = [
            ("frontend/src/**/*.tsx", "TypeScript React"),
            ("frontend/src/**/*.ts", "TypeScript"),
            ("frontend/src/**/*.css", "CSS"),
            ("backend/app/**/*.py", "Python"),
            ("backend/tests/**/*.py", "Python Test"),
        ]

        for pattern, lang in patterns:
            for f in sorted(root.glob(pattern)):
                rel = f.relative_to(root)
                try:
                    content = f.read_text(encoding="utf-8")
                    if len(content) > 10000:  # 너무 큰 파일은 건너뛰기
                        continue
                    files_content.append(f"### {rel}\n```{lang.lower()}\n{content}\n```")
                except (UnicodeDecodeError, PermissionError):
                    continue

        if not files_content:
            return ""

        return "## 현재 프로젝트 코드\n\n" + "\n\n".join(files_content) + "\n\n"

    def _invoke_gemini(self, step: dict, preamble: str) -> dict:
        step_num, step_name = step["step"], step["name"]
        step_file = self._phase_dir / f"step{step_num}.md"

        if not step_file.exists():
            print(f"  ERROR: {step_file} not found")
            sys.exit(1)

        # 프로젝트 파일 컨텍스트 수집
        project_context = self._collect_project_files()

        prompt = preamble + project_context + step_file.read_text()

        system_instruction = (
            "당신은 시니어 풀스택 개발자입니다. "
            "주어진 step 지시를 정확하게 수행하고, 필요한 코드를 작성하세요.\n\n"
            "## 응답 형식\n\n"
            "JSON 형식으로 응답하세요:\n"
            "```json\n"
            "{\n"
            '  "actions": [\n'
            "    {\n"
            '      "type": "create_file" | "modify_file" | "run_command",\n'
            '      "path": "파일 경로 (프로젝트 루트 기준)",\n'
            '      "content": "파일 전체 내용 (create_file/modify_file인 경우)",\n'
            '      "command": "실행할 커맨드 (run_command인 경우)",\n'
            '      "cwd": "커맨드 실행 디렉토리 (run_command인 경우, 선택사항)"\n'
            "    }\n"
            "  ],\n"
            '  "status": "completed" | "error" | "blocked",\n'
            '  "summary": "이 step에서 수행한 작업 한 줄 요약",\n'
            '  "error_message": "에러 시 상세 메시지 (선택사항)",\n'
            '  "blocked_reason": "차단 사유 (선택사항)"\n'
            "}\n"
            "```\n\n"
            "## 중요 규칙\n"
            "- 파일 경로는 프로젝트 루트 기준 상대 경로를 사용하세요.\n"
            "- create_file: 새 파일 생성 또는 기존 파일 덮어쓰기.\n"
            "- modify_file: 기존 파일 수정 (전체 내용 교체).\n"
            "- run_command: 테스트, 빌드, 패키지 설치 등의 명령어 실행.\n"
            "- 반드시 JSON 블록만 응답하세요. 다른 텍스트를 포함하지 마세요.\n"
        )

        try:
            model = genai.GenerativeModel(
                model_name=self.GEMINI_MODEL,
                generation_config=genai.GenerationConfig(
                    temperature=self.GEMINI_TEMPERATURE,
                    max_output_tokens=65536,
                ),
                system_instruction=system_instruction,
            )
            response = model.generate_content(prompt)

            response_text = response.text
            result = self._parse_and_apply_response(response_text, step_num, step_name)

        except Exception as e:
            result = {
                "step": step_num,
                "name": step_name,
                "error": str(e),
                "status": "error",
            }
            print(f"\n  WARN: Gemini 호출 실패: {e}")

        # 출력 저장
        out_path = self._phase_dir / f"step{step_num}-output.json"
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        return result

    def _parse_and_apply_response(self, response_text: str, step_num: int, step_name: str) -> dict:
        """Gemini 응답을 파싱하고 액션을 실행"""
        # JSON 블록 추출
        json_str = response_text
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0]

        try:
            data = json.loads(json_str.strip())
        except json.JSONDecodeError as e:
            return {
                "step": step_num,
                "name": step_name,
                "error": f"JSON 파싱 실패: {e}\nResponse: {response_text[:1000]}",
                "status": "error",
            }

        # 액션 실행
        actions = data.get("actions", [])
        for action in actions:
            action_type = action.get("type")
            try:
                if action_type in ("create_file", "modify_file"):
                    self._apply_file_action(action)
                elif action_type == "run_command":
                    self._apply_command_action(action)
            except Exception as e:
                print(f"  WARN: 액션 실행 실패 ({action_type}): {e}")

        # index.json 업데이트
        status = data.get("status", "pending")
        index = self._read_json(self._index_file)
        for s in index["steps"]:
            if s["step"] == step_num:
                s["status"] = status
                if status == "completed" and data.get("summary"):
                    s["summary"] = data["summary"]
                elif status == "error" and data.get("error_message"):
                    s["error_message"] = data["error_message"]
                elif status == "blocked" and data.get("blocked_reason"):
                    s["blocked_reason"] = data["blocked_reason"]
                break
        self._write_json(self._index_file, index)

        return {
            "step": step_num,
            "name": step_name,
            "status": status,
            "actions_count": len(actions),
            "summary": data.get("summary", ""),
            "response_length": len(response_text),
        }

    def _apply_file_action(self, action: dict):
        """파일 생성/수정 액션 적용"""
        path = Path(self._root) / action["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        content = action.get("content", "")
        path.write_text(content, encoding="utf-8")
        print(f"    📝 {action['path']}")

    def _apply_command_action(self, action: dict):
        """커맨드 실행 액션 적용"""
        cmd = action.get("command", "")
        cwd = action.get("cwd", self._root)
        if not os.path.isabs(cwd):
            cwd = os.path.join(self._root, cwd)

        # 위험한 명령어 차단
        dangerous_patterns = ["rm -rf", "git push --force", "git reset --hard", "DROP TABLE"]
        for pattern in dangerous_patterns:
            if pattern in cmd:
                print(f"    ⛔ 위험한 명령어 차단: {cmd}")
                return

        print(f"    🔧 {cmd}")
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            print(f"    ⚠ 명령어 실패 (exit {result.returncode}): {result.stderr[:300]}")

    # --- 헤더 & 검증 ---

    def _print_header(self):
        print(f"\n{'='*60}")
        print(f"  Harness Step Executor (Gemini)")
        print(f"  Phase: {self._phase_name} | Steps: {self._total}")
        print(f"  Model: {self.GEMINI_MODEL}")
        if self._auto_push:
            print(f"  Auto-push: enabled")
        print(f"{'='*60}")

    def _check_blockers(self):
        index = self._read_json(self._index_file)
        for s in reversed(index["steps"]):
            if s["status"] == "error":
                print(f"\n  ✗ Step {s['step']} ({s['name']}) failed.")
                print(f"  Error: {s.get('error_message', 'unknown')}")
                print(f"  Fix and reset status to 'pending' to retry.")
                sys.exit(1)
            if s["status"] == "blocked":
                print(f"\n  ⏸ Step {s['step']} ({s['name']}) blocked.")
                print(f"  Reason: {s.get('blocked_reason', 'unknown')}")
                print(f"  Resolve and reset status to 'pending' to retry.")
                sys.exit(2)
            if s["status"] != "pending":
                break

    def _ensure_created_at(self):
        index = self._read_json(self._index_file)
        if "created_at" not in index:
            index["created_at"] = self._stamp()
            self._write_json(self._index_file, index)

    # --- 실행 루프 ---

    def _execute_single_step(self, step: dict, guardrails: str) -> bool:
        """단일 step 실행 (재시도 포함). 완료되면 True, 실패/차단이면 False."""
        step_num, step_name = step["step"], step["name"]
        done = sum(1 for s in self._read_json(self._index_file)["steps"] if s["status"] == "completed")
        prev_error = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            index = self._read_json(self._index_file)
            step_context = self._build_step_context(index)
            preamble = self._build_preamble(guardrails, step_context, prev_error)

            tag = f"Step {step_num}/{self._total - 1} ({done} done): {step_name}"
            if attempt > 1:
                tag += f" [retry {attempt}/{self.MAX_RETRIES}]"

            with progress_indicator(tag) as pi:
                self._invoke_gemini(step, preamble)
                elapsed = int(pi.elapsed)

            index = self._read_json(self._index_file)
            status = next((s.get("status", "pending") for s in index["steps"] if s["step"] == step_num), "pending")
            ts = self._stamp()

            if status == "completed":
                for s in index["steps"]:
                    if s["step"] == step_num:
                        s["completed_at"] = ts
                self._write_json(self._index_file, index)
                self._commit_step(step_num, step_name)
                print(f"  ✓ Step {step_num}: {step_name} [{elapsed}s]")
                return True

            if status == "blocked":
                for s in index["steps"]:
                    if s["step"] == step_num:
                        s["blocked_at"] = ts
                self._write_json(self._index_file, index)
                reason = next((s.get("blocked_reason", "") for s in index["steps"] if s["step"] == step_num), "")
                print(f"  ⏸ Step {step_num}: {step_name} blocked [{elapsed}s]")
                print(f"    Reason: {reason}")
                self._update_top_index("blocked")
                sys.exit(2)

            err_msg = next(
                (s.get("error_message", "Step did not update status") for s in index["steps"] if s["step"] == step_num),
                "Step did not update status",
            )

            if attempt < self.MAX_RETRIES:
                for s in index["steps"]:
                    if s["step"] == step_num:
                        s["status"] = "pending"
                        s.pop("error_message", None)
                self._write_json(self._index_file, index)
                prev_error = err_msg
                print(f"  ↻ Step {step_num}: retry {attempt}/{self.MAX_RETRIES} — {err_msg}")
            else:
                for s in index["steps"]:
                    if s["step"] == step_num:
                        s["status"] = "error"
                        s["error_message"] = f"[{self.MAX_RETRIES}회 시도 후 실패] {err_msg}"
                        s["failed_at"] = ts
                self._write_json(self._index_file, index)
                self._commit_step(step_num, step_name)
                print(f"  ✗ Step {step_num}: {step_name} failed after {self.MAX_RETRIES} attempts [{elapsed}s]")
                print(f"    Error: {err_msg}")
                self._update_top_index("error")
                sys.exit(1)

        return False  # unreachable

    def _execute_all_steps(self, guardrails: str):
        while True:
            index = self._read_json(self._index_file)
            pending = next((s for s in index["steps"] if s["status"] == "pending"), None)
            if pending is None:
                print("\n  All steps completed!")
                return

            step_num = pending["step"]
            for s in index["steps"]:
                if s["step"] == step_num and "started_at" not in s:
                    s["started_at"] = self._stamp()
                    self._write_json(self._index_file, index)
                    break

            self._execute_single_step(pending, guardrails)

    def _finalize(self):
        index = self._read_json(self._index_file)
        index["completed_at"] = self._stamp()
        self._write_json(self._index_file, index)
        self._update_top_index("completed")

        self._run_git("add", "-A")
        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            msg = f"chore({self._phase_name}): mark phase completed"
            r = self._run_git("commit", "-m", msg)
            if r.returncode == 0:
                print(f"  ✓ {msg}")

        if self._auto_push:
            branch = f"feat-{self._phase_name}"
            r = self._run_git("push", "-u", "origin", branch)
            if r.returncode != 0:
                print(f"\n  ERROR: git push 실패: {r.stderr.strip()}")
                sys.exit(1)
            print(f"  ✓ Pushed to origin/{branch}")

        print(f"\n{'='*60}")
        print(f"  Phase '{self._phase_name}' completed!")
        print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="Harness Step Executor (Gemini)")
    parser.add_argument("phase_dir", help="Phase directory name (e.g. 0-mvp)")
    parser.add_argument("--push", action="store_true", help="Push branch after completion")
    args = parser.parse_args()

    StepExecutor(args.phase_dir, auto_push=args.push).run()


if __name__ == "__main__":
    main()
