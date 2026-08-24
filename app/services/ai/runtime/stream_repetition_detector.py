from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# 默认连续相同句子熔断阈值（连续 50 次即熔断）
DEFAULT_REPETITION_THRESHOLD = 50
# 默认参与重复判定的最小有效句子长度（字符数），避免误杀“好的”、“然后”等简短连词
DEFAULT_MIN_PHRASE_LEN = 6
# 未完成句子的最大缓存大小
DEFAULT_WINDOW_SIZE = 1000

# 句末标点正则。换行、逗号和 Markdown/代码符号不作为句子边界。
_SENTENCE_DELIMITERS_PATTERN = re.compile(r"[。！？；!?;.]+")


@dataclass
class RepetitionVerdict:
    """重复检测裁决结果。"""
    fused: bool = False
    repeated_phrase: str = ""
    repeat_count: int = 0
    message: str = ""


@dataclass
class StreamRepetitionDetector:
    """流式文本生成重复死循环熔断检测器 (Stream Repetition Detector)。

    用于在 SSE 流式生成或 Agent 思考旁白链路中，实时拦截大语言模型（LLM）
    陷入自回归局部死循环（Repetition Degeneration）。

    检测策略：
    仅对句末标点分隔出的完整句子进行连续重复检测。达到 ``threshold``（默认 50）次的
    相同句子会触发熔断；无标点片段、Markdown、代码和其他字符模式不参与判断。
    """
    threshold: int = DEFAULT_REPETITION_THRESHOLD
    min_phrase_len: int = DEFAULT_MIN_PHRASE_LEN
    window_size: int = DEFAULT_WINDOW_SIZE

    _buffer: str = field(default="", init=False)
    _last_phrase: str = field(default="", init=False)
    _repeat_count: int = field(default=0, init=False)
    _fused: bool = field(default=False, init=False)
    _fused_verdict: Optional[RepetitionVerdict] = field(default=None, init=False)

    @property
    def is_fused(self) -> bool:
        return self._fused

    def reset(self) -> None:
        """重置检测器状态（用于新一轮调用或工具执行后）。"""
        self._buffer = ""
        self._last_phrase = ""
        self._repeat_count = 0
        self._fused = False
        self._fused_verdict = None

    def _normalize_phrase(self, text: str) -> str:
        """归一化句子：去除两端空白与常见标点，折叠连续空白。"""
        cleaned = re.sub(r"\s+", " ", text).strip()
        cleaned = cleaned.strip(" \t\n\r。，！？；：\"'“”‘’(),.!?;:[]{}（）")
        return cleaned

    def feed(self, delta: str) -> RepetitionVerdict:
        """接收流式文本增量，只评估其中已经结束的完整句子。"""
        if self._fused and self._fused_verdict is not None:
            return self._fused_verdict

        if not delta:
            return RepetitionVerdict(fused=False)

        self._buffer += str(delta)

        # 只切出已经遇到句末标点的完整句子，保留末尾未完成句子等待下一次增量。
        pieces = _SENTENCE_DELIMITERS_PATTERN.split(self._buffer)
        if len(pieces) == 1:
            if len(self._buffer) > self.window_size:
                self._buffer = self._buffer[-self.window_size:]
            return RepetitionVerdict(fused=False, repeat_count=self._repeat_count)

        complete_pieces = pieces[:-1]
        self._buffer = pieces[-1]

        for piece in complete_pieces:
            normalized = self._normalize_phrase(piece)
            if len(normalized) < self.min_phrase_len:
                # 短插话/连接词是连续输出序列中的边界，不能被忽略。
                self._last_phrase = ""
                self._repeat_count = 0
                continue

            if normalized == self._last_phrase:
                self._repeat_count += 1
            else:
                self._last_phrase = normalized
                self._repeat_count = 1

            if self._repeat_count >= self.threshold:
                self._fused = True
                verdict = RepetitionVerdict(
                    fused=True,
                    repeated_phrase=self._last_phrase,
                    repeat_count=self._repeat_count,
                    message=(
                        f"检测到模型连续重复输出相同句子「{self._last_phrase[:30]}」"
                        f"达 {self._repeat_count} 次，已触发防刷屏流式截断。"
                    ),
                )
                self._fused_verdict = verdict
                logger.warning(
                    "[StreamRepetitionDetector] Sentence fused: phrase='%s' count=%d",
                    verdict.repeated_phrase,
                    verdict.repeat_count,
                )
                return verdict

        if len(self._buffer) > self.window_size:
            self._buffer = self._buffer[-self.window_size:]
        return RepetitionVerdict(fused=False, repeat_count=self._repeat_count)
