#!/usr/bin/env python3
"""
implement-review-loop — state_manager.py 测试脚本

运行方式：
  cd tests/ && python test_all.py

测试覆盖：
  1. init 命令（正常初始化、重复初始化、自定义参数）
  2. record 命令（正常记录、多轮记录、备注、边界分数）
  3. status 命令（空状态、有数据、平台期、达标、超轮次）
  4. history 命令（JSON 输出、空状态）
  5. feedback 命令（追加、多次追加）
  6. 边界情况（无状态目录、中文内容、Unicode 路径）
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

# ── 路径配置 ──────────────────────────────────────────

TESTS_DIR = Path(__file__).parent
SKILL_DIR = TESTS_DIR.parent
SCRIPT = SKILL_DIR / "scripts" / "state_manager.py"
WORK_DIR = TESTS_DIR / "_work"

# ── 工具函数 ──────────────────────────────────────────

passed = 0
failed = 0
errors = []


def run(args, expect_exit=0):
    """运行 state_manager.py 命令，返回 (stdout, exit_code)"""
    cmd = [sys.executable, str(SCRIPT)] + args
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != expect_exit:
        errors.append(f"  ⚠️ Expected exit {expect_exit}, got {result.returncode}")
        errors.append(f"     stderr: {result.stderr.strip()}")
    return result.stdout.strip(), result.returncode


def assert_eq(name, actual, expected):
    global passed, failed
    if actual == expected:
        passed += 1
        print(f"  ✅ {name}")
        return True
    else:
        failed += 1
        print(f"  ❌ {name}")
        print(f"     expected: {expected}")
        print(f"     actual:   {actual}")
        return False


def assert_contains(name, text, substring):
    global passed, failed
    if substring in text:
        passed += 1
        print(f"  ✅ {name}")
        return True
    else:
        failed += 1
        print(f"  ❌ {name}")
        print(f"     expected to contain: {substring}")
        print(f"     actual: {text[:200]}")
        return False


def assert_file_exists(name, path):
    global passed, failed
    if Path(path).exists():
        passed += 1
        print(f"  ✅ {name}")
        return True
    else:
        failed += 1
        print(f"  ❌ {name}")
        print(f"     file not found: {path}")
        return False


def assert_json_valid(name, text):
    """验证文本是合法 JSON 并返回解析结果"""
    global passed, failed
    try:
        data = json.loads(text)
        passed += 1
        print(f"  ✅ {name}")
        return data
    except json.JSONDecodeError as e:
        failed += 1
        print(f"  ❌ {name}")
        print(f"     invalid JSON: {e}")
        return None


def setup():
    """清理并创建工作目录"""
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    WORK_DIR.mkdir(parents=True)


def teardown():
    """清理工作目录"""
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)


# ── 测试用例 ──────────────────────────────────────────

def test_help():
    """T01: help 命令输出包含所有命令名"""
    print("\n── T01: help 命令 ──")
    out, code = run(["help"])
    assert_eq("exit code", code, 0)
    for cmd in ["init", "record", "status", "history", "feedback"]:
        assert_contains(f"help 包含 '{cmd}'", out, cmd)


def test_init_basic():
    """T02: 基本初始化"""
    print("\n── T02: 基本初始化 ──")
    setup()
    try:
        project = str(WORK_DIR / "proj1")
        out, code = run(["init", "--project", project, "--target", "90", "--max-rounds", "5"])
        assert_eq("exit code", code, 0)
        assert_contains("输出包含 Created feedback.md", out, "Created feedback.md")
        assert_contains("输出包含 Created round-history.json", out, "Created round-history.json")
        assert_contains("输出包含 Target: 90", out, "Target: 90")
        assert_contains("输出包含 Max rounds: 5", out, "Max rounds: 5")
        assert_file_exists("feedback.md 存在", Path(project) / ".iteration-state" / "feedback.md")
        assert_file_exists("round-history.json 存在", Path(project) / ".iteration-state" / "round-history.json")

        # 验证 JSON 内容
        json_path = Path(project) / ".iteration-state" / "round-history.json"
        data = assert_json_valid("JSON 合法", json_path.read_text(encoding="utf-8"))
        if data:
            assert_eq("rounds 为空", data["rounds"], [])
            assert_eq("target_score", data["target_score"], 90)
            assert_eq("max_rounds", data["max_rounds"], 5)

        # 验证 feedback.md 内容
        fb = Path(project) / ".iteration-state" / "feedback.md"
        assert_contains("feedback 包含标题", fb.read_text(encoding="utf-8"), "# Iteration Feedback")
    finally:
        teardown()


def test_init_reinit():
    """T03: 重复初始化不覆盖已有文件"""
    print("\n── T03: 重复初始化 ──")
    setup()
    try:
        project = str(WORK_DIR / "proj2")
        run(["init", "--project", project, "--target", "90", "--max-rounds", "5"])
        fb_path = Path(project) / ".iteration-state" / "feedback.md"
        fb_path.write_text("# Custom Content\n", encoding="utf-8")

        out, code = run(["init", "--project", project, "--target", "85", "--max-rounds", "3"])
        assert_eq("exit code", code, 0)
        assert_contains("输出提示 skipped", out, "skipped")

        content = fb_path.read_text(encoding="utf-8")
        assert_eq("feedback.md 保留自定义内容", content, "# Custom Content\n")

        json_path = Path(project) / ".iteration-state" / "round-history.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert_eq("target_score 保留原值", data["target_score"], 90)
    finally:
        teardown()


def test_init_custom_params():
    """T04: 自定义参数"""
    print("\n── T04: 自定义参数 ──")
    setup()
    try:
        project = str(WORK_DIR / "proj3")
        out, code = run(["init", "--project", project, "--target", "80", "--max-rounds", "10"])
        assert_eq("exit code", code, 0)
        assert_contains("输出包含 Target: 80", out, "Target: 80")
        assert_contains("输出包含 Max rounds: 10", out, "Max rounds: 10")

        json_path = Path(project) / ".iteration-state" / "round-history.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert_eq("target_score=80", data["target_score"], 80)
        assert_eq("max_rounds=10", data["max_rounds"], 10)
    finally:
        teardown()


def test_init_defaults():
    """T05: 默认参数（不指定 target 和 max-rounds）"""
    print("\n── T05: 默认参数 ──")
    setup()
    try:
        project = str(WORK_DIR / "proj_default")
        out, code = run(["init", "--project", project])
        assert_eq("exit code", code, 0)
        assert_contains("默认 Target: 90", out, "Target: 90")
        assert_contains("默认 Max rounds: 5", out, "Max rounds: 5")
    finally:
        teardown()


def test_record_basic():
    """T06: 基本记录"""
    print("\n── T06: 基本记录 ──")
    setup()
    try:
        project = str(WORK_DIR / "proj4")
        run(["init", "--project", project])

        out, code = run(["record", "--project", project, "--score", "72", "--critical", "3", "--minor", "2"])
        assert_eq("exit code", code, 0)
        assert_contains("输出包含 Round 1", out, "Round 1")
        assert_contains("输出包含 score=72", out, "score=72")
        assert_contains("输出包含 Gap: 18", out, "Gap: 18")

        json_path = Path(project) / ".iteration-state" / "round-history.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert_eq("rounds 长度", len(data["rounds"]), 1)
        assert_eq("第1轮 score", data["rounds"][0]["score"], 72)
        assert_eq("第1轮 critical_fixes", data["rounds"][0]["critical_fixes"], 3)
        assert_eq("第1轮 minor_fixes", data["rounds"][0]["minor_fixes"], 2)
    finally:
        teardown()


def test_record_multiple_rounds():
    """T07: 多轮记录"""
    print("\n── T07: 多轮记录 ──")
    setup()
    try:
        project = str(WORK_DIR / "proj5")
        run(["init", "--project", project, "--target", "90", "--max-rounds", "5"])

        run(["record", "--project", project, "--score", "68", "--critical", "3", "--minor", "2"])
        out2, _ = run(["record", "--project", project, "--score", "81", "--critical", "2", "--minor", "1"])
        assert_contains("Round 2", out2, "Round 2")
        assert_contains("+13 提升", out2, "+13")

        run(["record", "--project", project, "--score", "85", "--critical", "1", "--minor", "1"])

        json_path = Path(project) / ".iteration-state" / "round-history.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert_eq("3 轮记录", len(data["rounds"]), 3)
        assert_eq("分数序列", [r["score"] for r in data["rounds"]], [68, 81, 85])
    finally:
        teardown()


def test_record_with_note():
    """T08: 带备注的记录"""
    print("\n── T08: 带备注 ──")
    setup()
    try:
        project = str(WORK_DIR / "proj_note")
        run(["init", "--project", project])
        out, code = run(["record", "--project", project, "--score", "75", "--note", "第一轮测试"])
        assert_eq("exit code", code, 0)

        json_path = Path(project) / ".iteration-state" / "round-history.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert_eq("note 字段", data["rounds"][0]["note"], "第一轮测试")
    finally:
        teardown()


def test_record_boundary_scores():
    """T09: 边界分数（0 和 100）"""
    print("\n── T09: 边界分数 ──")
    setup()
    try:
        project = str(WORK_DIR / "proj_boundary")
        run(["init", "--project", project, "--target", "100", "--max-rounds", "10"])

        out0, _ = run(["record", "--project", project, "--score", "0", "--critical", "0", "--minor", "0"])
        assert_contains("score=0", out0, "score=0")

        out100, _ = run(["record", "--project", project, "--score", "100", "--critical", "0", "--minor", "0"])
        assert_contains("TARGET REACHED", out100, "TARGET REACHED")

        json_path = Path(project) / ".iteration-state" / "round-history.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert_eq("分数记录", [r["score"] for r in data["rounds"]], [0, 100])
    finally:
        teardown()


def test_record_target_reached():
    """T10: 达到目标分数"""
    print("\n── T10: 达到目标分数 ──")
    setup()
    try:
        project = str(WORK_DIR / "proj_target")
        run(["init", "--project", project, "--target", "85", "--max-rounds", "5"])

        run(["record", "--project", project, "--score", "72", "--critical", "3", "--minor", "2"])
        out, _ = run(["record", "--project", project, "--score", "88", "--critical", "1", "--minor", "0"])
        assert_contains("TARGET REACHED", out, "TARGET REACHED")
    finally:
        teardown()


def test_record_max_rounds():
    """T11: 达到最大轮次"""
    print("\n── T11: 达到最大轮次 ──")
    setup()
    try:
        project = str(WORK_DIR / "proj_max")
        run(["init", "--project", project, "--target", "100", "--max-rounds", "3"])

        run(["record", "--project", project, "--score", "70", "--critical", "3", "--minor", "2"])
        run(["record", "--project", project, "--score", "78", "--critical", "2", "--minor", "1"])
        out, _ = run(["record", "--project", project, "--score", "82", "--critical", "1", "--minor", "1"])
        assert_contains("Max rounds", out, "Max rounds")
    finally:
        teardown()


def test_record_plateau_detection():
    """T12: 平台期检测"""
    print("\n── T12: 平台期检测 ──")
    setup()
    try:
        project = str(WORK_DIR / "proj_plateau")
        run(["init", "--project", project, "--target", "90", "--max-rounds", "5"])

        run(["record", "--project", project, "--score", "72", "--critical", "3", "--minor", "2"])
        run(["record", "--project", project, "--score", "81", "--critical", "2", "--minor", "1"])
        out3, _ = run(["record", "--project", project, "--score", "81", "--critical", "1", "--minor", "2"])
        assert_contains("plateau 1/2", out3, "plateau 1/2")

        out4, _ = run(["record", "--project", project, "--score", "80", "--critical", "1", "--minor", "2"])
        assert_contains("PLATEAU", out4, "PLATEAU")
    finally:
        teardown()


def test_record_no_init():
    """T13: 未初始化就 record"""
    print("\n── T13: 未初始化就 record ──")
    setup()
    try:
        project = str(WORK_DIR / "proj_no_init")
        out, code = run(["record", "--project", project, "--score", "70"], expect_exit=1)
        assert_eq("exit code=1", code, 1)
        assert_contains("提示 init", out, "Run `init` first")
    finally:
        teardown()


def test_status_empty():
    """T14: 空状态 status"""
    print("\n── T14: 空状态 status ──")
    setup()
    try:
        project = str(WORK_DIR / "proj_status_empty")
        run(["init", "--project", project])

        out, code = run(["status", "--project", project])
        assert_eq("exit code", code, 0)
        assert_contains("Rounds completed: 0/5", out, "Rounds completed: 0/5")
        assert_contains("No rounds yet", out, "No rounds yet")
    finally:
        teardown()


def test_status_with_data():
    """T15: 有数据的 status"""
    print("\n── T15: 有数据的 status ──")
    setup()
    try:
        project = str(WORK_DIR / "proj_status")
        run(["init", "--project", project, "--target", "90", "--max-rounds", "5"])
        run(["record", "--project", project, "--score", "68", "--critical", "3", "--minor", "2"])
        run(["record", "--project", project, "--score", "81", "--critical", "2", "--minor", "1"])

        out, code = run(["status", "--project", project])
        assert_eq("exit code", code, 0)
        assert_contains("Rounds completed: 2/5", out, "Rounds completed: 2/5")
        assert_contains("68", out, "68")
        assert_contains("81", out, "81")
        assert_contains("IN PROGRESS", out, "IN PROGRESS")
    finally:
        teardown()


def test_status_plateau():
    """T16: status 显示平台期"""
    print("\n── T16: status 平台期 ──")
    setup()
    try:
        project = str(WORK_DIR / "proj_status_plat")
        run(["init", "--project", project, "--target", "90", "--max-rounds", "5"])
        run(["record", "--project", project, "--score", "72", "--critical", "3", "--minor", "2"])
        run(["record", "--project", project, "--score", "81", "--critical", "2", "--minor", "1"])
        run(["record", "--project", project, "--score", "81", "--critical", "1", "--minor", "2"])

        out, _ = run(["status", "--project", project])
        assert_contains("PLATEAU WARNING", out, "PLATEAU WARNING")
    finally:
        teardown()


def test_status_target_reached():
    """T17: status 显示达标"""
    print("\n── T17: status 达标 ──")
    setup()
    try:
        project = str(WORK_DIR / "proj_status_ok")
        run(["init", "--project", project, "--target", "85", "--max-rounds", "5"])
        run(["record", "--project", project, "--score", "72", "--critical", "3", "--minor", "2"])
        run(["record", "--project", project, "--score", "90", "--critical", "0", "--minor", "1"])

        out, _ = run(["status", "--project", project])
        assert_contains("TARGET REACHED", out, "TARGET REACHED")
    finally:
        teardown()


def test_status_no_init():
    """T18: 未初始化就 status"""
    print("\n── T18: 未初始化就 status ──")
    setup()
    try:
        project = str(WORK_DIR / "proj_no_init2")
        out, code = run(["status", "--project", project], expect_exit=1)
        assert_eq("exit code=1", code, 1)
    finally:
        teardown()


def test_history_basic():
    """T19: history JSON 输出"""
    print("\n── T19: history 基本输出 ──")
    setup()
    try:
        project = str(WORK_DIR / "proj_hist")
        run(["init", "--project", project, "--target", "90", "--max-rounds", "5"])
        run(["record", "--project", project, "--score", "72", "--critical", "3", "--minor", "2"])

        out, code = run(["history", "--project", project])
        assert_eq("exit code", code, 0)
        data = assert_json_valid("输出是合法 JSON", out)
        if data:
            assert_eq("rounds 长度", len(data["rounds"]), 1)
            assert_eq("target_score", data["target_score"], 90)
    finally:
        teardown()


def test_history_empty():
    """T20: 无状态时 history"""
    print("\n── T20: 无状态 history ──")
    setup()
    try:
        project = str(WORK_DIR / "proj_hist_empty")
        out, _ = run(["history", "--project", project])
        assert_eq("输出 {}", out, "{}")
    finally:
        teardown()


def test_feedback_append():
    """T21: feedback 追加"""
    print("\n── T21: feedback 追加 ──")
    setup()
    try:
        project = str(WORK_DIR / "proj_fb")
        run(["init", "--project", project])

        out1, _ = run(["feedback", "--project", project, "--append", "## Round 1\nScore: 72"])
        assert_contains("Appended", out1, "Appended")

        out2, _ = run(["feedback", "--project", project, "--append", "## Round 2\nScore: 81"])
        assert_contains("Appended", out2, "Appended")

        fb_path = Path(project) / ".iteration-state" / "feedback.md"
        content = fb_path.read_text(encoding="utf-8")
        assert_contains("包含 Round 1", content, "Round 1")
        assert_contains("包含 Round 2", content, "Round 2")
    finally:
        teardown()


def test_feedback_no_content():
    """T22: feedback 不带 --append"""
    print("\n── T22: feedback 无内容 ──")
    setup()
    try:
        project = str(WORK_DIR / "proj_fb2")
        run(["init", "--project", project])
        out, code = run(["feedback", "--project", project], expect_exit=1)
        assert_eq("exit code=1", code, 1)
    finally:
        teardown()


def test_feedback_no_init():
    """T23: 未初始化就 feedback"""
    print("\n── T23: 未初始化 feedback ──")
    setup()
    try:
        project = str(WORK_DIR / "proj_fb3")
        out, code = run(["feedback", "--project", project, "--append", "test"], expect_exit=1)
        assert_eq("exit code=1", code, 1)
    finally:
        teardown()


def test_full_workflow():
    """T24: 完整工作流（init → record × 3 → status → feedback → history）"""
    print("\n── T24: 完整工作流 ──")
    setup()
    try:
        project = str(WORK_DIR / "proj_full")

        out_init, _ = run(["init", "--project", project, "--target", "90", "--max-rounds", "5"])
        assert_contains("初始化成功", out_init, "Created")

        out_r1, _ = run(["record", "--project", project, "--score", "68", "--critical", "3", "--minor", "2"])
        assert_contains("Round 1", out_r1, "Round 1")

        run(["feedback", "--project", project, "--append", "## Round 1 — Score: 68/100\n### Critical\n1. scripts/ 无错误处理"])

        out_r2, _ = run(["record", "--project", project, "--score", "81", "--critical", "2", "--minor", "1"])
        assert_contains("+13", out_r2, "+13")

        run(["feedback", "--project", project, "--append", "## Round 2 — Score: 81/100\n### Fixed\n- scripts/ 错误处理 ✅"])

        out_r3, _ = run(["record", "--project", project, "--score", "92", "--critical", "0", "--minor", "1"])
        assert_contains("TARGET REACHED", out_r3, "TARGET REACHED")

        out_status, _ = run(["status", "--project", project])
        assert_contains("TARGET REACHED", out_status, "TARGET REACHED")
        assert_contains("3/5", out_status, "3/5")

        out_hist, _ = run(["history", "--project", project])
        data = json.loads(out_hist)
        assert_eq("3 轮", len(data["rounds"]), 3)
        assert_eq("最终分数", data["rounds"][-1]["score"], 92)

        fb_path = Path(project) / ".iteration-state" / "feedback.md"
        content = fb_path.read_text(encoding="utf-8")
        assert_contains("feedback 含 Round 1", content, "Round 1")
        assert_contains("feedback 含 Round 2", content, "Round 2")
    finally:
        teardown()


def test_chinese_content():
    """T25: 中文内容支持"""
    print("\n── T25: 中文内容 ──")
    setup()
    try:
        project = str(WORK_DIR / "proj_cn")
        run(["init", "--project", project])
        run(["record", "--project", project, "--score", "75", "--note", "第一轮：脚本缺少错误处理"])
        run(["feedback", "--project", project, "--append", "## 第1轮评审\n**扣分项**：scripts/ 无错误处理\n**修复建议**：添加空输入检查"])

        json_path = Path(project) / ".iteration-state" / "round-history.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert_eq("中文 note", data["rounds"][0]["note"], "第一轮：脚本缺少错误处理")

        fb_path = Path(project) / ".iteration-state" / "feedback.md"
        content = fb_path.read_text(encoding="utf-8")
        assert_contains("中文扣分项", content, "扣分项")
        assert_contains("中文修复建议", content, "修复建议")
    finally:
        teardown()


def test_unicode_path():
    """T26: Unicode 路径支持"""
    print("\n── T26: Unicode 路径 ──")
    setup()
    try:
        project = str(WORK_DIR / "项目_测试")
        out, code = run(["init", "--project", project])
        assert_eq("exit code", code, 0)
        assert_file_exists("feedback.md", Path(project) / ".iteration-state" / "feedback.md")

        run(["record", "--project", project, "--score", "80"])
        out_status, _ = run(["status", "--project", project])
        assert_contains("Rounds completed: 1", out_status, "Rounds completed: 1")
    finally:
        teardown()


# ── 主入口 ────────────────────────────────────────────

def main():
    global passed, failed, errors

    print("=" * 60)
    print("implement-review-loop — state_manager.py 测试")
    print("=" * 60)
    print(f"脚本路径: {SCRIPT}")
    print(f"工作目录: {WORK_DIR}")
    print()

    tests = [
        test_help,
        test_init_basic,
        test_init_reinit,
        test_init_custom_params,
        test_init_defaults,
        test_record_basic,
        test_record_multiple_rounds,
        test_record_with_note,
        test_record_boundary_scores,
        test_record_target_reached,
        test_record_max_rounds,
        test_record_plateau_detection,
        test_record_no_init,
        test_status_empty,
        test_status_with_data,
        test_status_plateau,
        test_status_target_reached,
        test_status_no_init,
        test_history_basic,
        test_history_empty,
        test_feedback_append,
        test_feedback_no_content,
        test_feedback_no_init,
        test_full_workflow,
        test_chinese_content,
        test_unicode_path,
    ]

    for test in tests:
        try:
            test()
        except Exception as e:
            failed += 1
            print(f"  💥 {test.__name__} 异常: {e}")
            errors.append(f"  💥 {test.__name__}: {e}")

    print()
    print("=" * 60)
    total = passed + failed
    print(f"📊 测试结果: ✅ {passed} passed / ❌ {failed} failed / 共 {total} 断言")
    print(f"📋 测试用例: {len(tests)} 个")

    if errors:
        print()
        print("── 错误详情 ──")
        for e in errors:
            print(e)

    print()
    if failed == 0:
        print("🎉 ALL TESTS PASSED!")
    else:
        print(f"⚠️ {failed} assertions failed")

    teardown()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
