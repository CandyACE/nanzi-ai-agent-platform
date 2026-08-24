from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# 默认连续相同短语/句子熔断阈值（连续 3 次即熔断）
DEFAULT_REPETITION_THRESHOLD = 3
# 默认参与重复判定的最小有效短语长度（字符数），避免误杀“好的”、“然后”等简短连词
DEFAULT_MIN_PHRASE_LEN = 6
# 用于无标点连写检测的最小子串长度
DEFAULT_MIN_NGRAM_LEN = 6
# 用于无标点连写的最大子串长度
DEFAULT_MAX_NGRAM_LEN = 60
# 滑动文本检测窗口大小
DEFAULT_WINDOW_SIZE = 1000

# 标点与换行分隔正则
_SENTENCE_DELIMITERS_PATTERN = re.compile(r"[\n\r。！？；!?;，,]+")


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
    1. **分句与短语连续重复检测 (Sentence/Phrase Repetition)**：
       通过中英文标点与换行对流式文本进行切分，若连续产生达到 ``threshold``（默认 3）次
       相同的有效语义短语（长度 >= ``min_phrase_len``），立即判定熔断。
    2. **无标点连续子串重复检测 (N-gram Periodicity)**：
       针对模型在没有标点分隔情况下无缝连续拼接重复句子的情形（如 ``"abcdeabcdeabcde"``），
       在滑动文本窗口末尾扫描重复周期，达到 ``threshold`` 次即判定熔断。
    """
    threshold: int = DEFAULT_REPETITION_THRESHOLD
    min_phrase_len: int = DEFAULT_MIN_PHRASE_LEN
    min_ngram_len: int = DEFAULT_MIN_NGRAM_LEN
    max_ngram_len: int = DEFAULT_MAX_NGRAM_LEN
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
        """归一化短语：去除两端空白与常见标点，折叠连续空白。"""
        cleaned = re.sub(r"\s+", " ", text).strip()
        cleaned = cleaned.strip(" \t\n\r。，！？；：\"'“”‘’(),.!?;:[]{}（）")
        return cleaned

    def _check_ngram_repetition(self, text: str) -> Optional[RepetitionVerdict]:
        """检查滑动文本末尾是否存在无标点连写的周期性重复短语。"""
        text_len = len(text)
        if text_len < self.min_ngram_len * self.threshold:
            return None

        # 从最大可能子串长度逆向扫描到最小长度
        max_scan = min(self.max_ngram_len, text_len // self.threshold)
        for sub_len in range(max_scan, self.min_ngram_len - 1, -1):
            pattern = text[-sub_len:]
            normalized_pattern = self._normalize_phrase(pattern)
            if len(normalized_pattern) < self.min_phrase_len:
                continue

            repeated_block = pattern * self.threshold
            if text.endswith(repeated_block):
                return RepetitionVerdict(
                    fused=True,
                    repeated_phrase=normalized_pattern,
                    repeat_count=self.threshold,
                    message=(
                        f"检测到模型无标点连续重复输出「{normalized_pattern[:30]}」"
                        f"达 {self.threshold} 次，已触发防刷屏流式截断。"
                    ),
                )
        return None

    def feed(self, delta: str) -> RepetitionVerdict:
        """接收流式文本增量并评估是否触发重复死循环熔断。"""
        if self._fused and self._fused_verdict is not None:
            return self._fused_verdict

        if not delta:
            return RepetitionVerdict(fused=False)

        self._buffer += str(delta)
        if len(self._buffer) > self.window_size:
            self._buffer = self._buffer[-self.window_size:]

        # 1. 首先检查末尾无标点周期性重复
        ngram_verdict = self._check_ngram_repetition(self._buffer)
        if ngram_verdict and ngram_verdict.fused:
            self._fused = True
            self._fused_verdict = ngram_verdict
            logger.warning(
                "[StreamRepetitionDetector] N-gram fused: phrase='%s' count=%d",
                ngram_verdict.repeated_phrase,
                ngram_verdict.repeat_count,
            )
            return ngram_verdict

        # 2. 检查分句/短语连续重复
        # 将 buffer 按分隔符切分成若干片段
        pieces = _SENTENCE_DELIMITERS_PATTERN.split(self._buffer)
        if pieces:
            # 评估最近的完整短语片段
            complete_pieces = [p for p in pieces[:-1] if p] if len(pieces) > 1 else []
            # 如果末尾刚好是分隔符结尾，则所有非空片段都是完整的
            if _SENTENCE_DELIMITERS_PATTERN.search(self._buffer[-1:] or ""):
                complete_pieces = [p for p in pieces if p]

            if complete_pieces:
                # 重新扫描完整片段计算重复
                cur_last = ""
                cur_count = 0
                for piece in complete_pieces:
                    normalized = self._normalize_phrase(piece)
                    if len(normalized) < self.min_phrase_len:
                        # 短插话/连接词仍然是连续输出序列中的边界，不能被
                        # 跳过后把前后两段相同长句拼成连续重复。
                        cur_last = ""
                        cur_count = 0
                        continue
                    if normalized == cur_last:
                        cur_count += 1
                    else:
                        cur_last = normalized
                        cur_count = 1

                    if cur_count >= self.threshold:
                        self._fused = True
                        verdict = RepetitionVerdict(
                            fused=True,
                            repeated_phrase=cur_last,
                            repeat_count=cur_count,
                            message=(
                                f"检测到模型连续重复输出相同短语「{cur_last[:30]}」"
                                f"达 {cur_count} 次，已触发防刷屏流式截断。"
                            ),
                        )
                        self._fused_verdict = verdict
                        logger.warning(
                            "[StreamRepetitionDetector] Phrase fused: phrase='%s' count=%d",
                            verdict.repeated_phrase,
                            verdict.repeat_count,
                        )
                        return verdict

                self._last_phrase = cur_last
                self._repeat_count = cur_count

        return RepetitionVerdict(fused=False, repeat_count=self._repeat_count)
