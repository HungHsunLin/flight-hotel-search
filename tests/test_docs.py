"""文件結構的漂移防呆。

散文沒辦法從單一來源生成多種語言，所以這裡退而求其次：**讓漂移沒辦法悄悄發生**。
各語言版本的標題層級序列必須一模一樣——只要有人只改了其中一份，CI 就會紅。

比的是層級序列（['##', '##', '###', ...]）而不是數量，因為數量對得上、順序卻換了
的情況同樣是漂移。標題文字本身當然不比——那是翻譯，本來就該不一樣。

歷史上這個破口出現過兩次，都在 SKILL.en.md：第一次少了 references/local.md 的
指令，第二次少了整組「會員 → 攤開品牌 / 訂房頁延遲載入」的操作規則。兩次都是
功能性缺陷（英文版會產生錯誤結論），兩次都是人工比對才發現的。
"""

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKILL_SET = ['SKILL.md', 'SKILL.en.md']
README_SET = ['README.md', 'README.zh-TW.md', 'README.ja.md']

_FENCE = re.compile(r'^\s*```')
_HEADING = re.compile(r'^(#{1,6}) \S')


def heading_levels(filename):
    """回傳該檔的標題層級序列。

    圍欄程式區塊要先剝掉：區塊裡的 `# 註解` 和 `## 分隔線` 不是標題，
    算進去會讓測試依 shell 註解的寫法而時好時壞。
    """
    levels = []
    in_fence = False
    with open(os.path.join(ROOT, filename), encoding='utf-8') as fh:
        for line in fh:
            if _FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            m = _HEADING.match(line)
            if m:
                levels.append(m.group(1))
    return levels


class TestDocumentStructure(unittest.TestCase):

    def testSkillTranslationsWhenComparedHaveIdenticalHeadingStructure(self):
        # Given: 中英文兩份 SKILL 是同一份操作規則的兩種語言
        reference = SKILL_SET[0]
        expected = heading_levels(reference)
        # When / Then: 每一份的標題層級序列都必須與基準相同
        for name in SKILL_SET[1:]:
            actual = heading_levels(name)
            self.assertEqual(
                expected, actual,
                '%s 與 %s 的標題結構不一致（%d vs %d 個標題）——'
                '有一份被單獨改過。兩份都要更新。' % (
                    reference, name, len(expected), len(actual)))

    def testReadmeTranslationsWhenComparedHaveIdenticalHeadingStructure(self):
        # Given: 三份 README 是同一份說明的三種語言
        reference = README_SET[0]
        expected = heading_levels(reference)
        # When / Then: 每一份的標題層級序列都必須與基準相同
        for name in README_SET[1:]:
            actual = heading_levels(name)
            self.assertEqual(
                expected, actual,
                '%s 與 %s 的標題結構不一致（%d vs %d 個標題）——'
                '有一份被單獨改過。三份都要更新。' % (
                    reference, name, len(expected), len(actual)))

    def testHeadingScannerWhenFileHasFencedCodeBlockThenIgnoresCommentsInside(self):
        # Given: SKILL.md 的程式區塊裡有以 # 開頭的 shell 註解
        raw = open(os.path.join(ROOT, 'SKILL.md'), encoding='utf-8').read()
        self.assertIn('```', raw, 'SKILL.md 應該有圍欄程式區塊，這個測試才有意義')
        # When: 掃描標題
        levels = heading_levels('SKILL.md')
        # Then: 只數到真正的標題，數量與 grep 掉程式區塊後的結果一致
        self.assertEqual(1, levels.count('#'), 'SKILL.md 應該只有一個 H1')
        self.assertTrue(all(len(lv) <= 3 for lv in levels),
                        '本專案的文件只用到 H1-H3；出現更深層代表結構走樣')


if __name__ == '__main__':
    unittest.main()
