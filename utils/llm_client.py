"""
统一 LLM 客户端封装
支持 OpenAI / 通义千问 / DeepSeek 三套 API，底层均兼容 OpenAI SDK 格式。
提供 JSON 模式调用、重试机制、结构化输出解析。
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)


class LLMClient:
    """统一 LLM 调用客户端，支持多提供商切换"""

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "openai").lower()

        if self.provider == "openai":
            self.api_key = os.getenv("OPENAI_API_KEY")
            self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        elif self.provider == "qwen":
            self.api_key = os.getenv("QWEN_API_KEY")
            self.base_url = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
            self.model = os.getenv("QWEN_MODEL", "qwen-turbo")
        elif self.provider == "deepseek":
            self.api_key = os.getenv("DEEPSEEK_API_KEY")
            self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
            self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        else:
            raise ValueError(f"不支持的 LLM 提供商: {self.provider}")

        if not self.api_key:
            raise ValueError(f"未设置 {self.provider.upper()}_API_KEY 环境变量，请检查 .env 文件")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        logger.info(f"LLM 客户端初始化完成，提供商: {self.provider}, 模型: {self.model}")

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> str:
        """
        通用对话调用

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            temperature: 温度参数
            max_tokens: 最大 token 数
            json_mode: 是否启用 JSON 模式

        Returns:
            模型回复文本
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        extra = {}
        # DeepSeek / Qwen 均支持 response_format，OpenAI 也支持
        if json_mode:
            extra["response_format"] = {"type": "json_object"}

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **extra,
        )
        return response.choices[0].message.content

    def chat_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        json_mode: bool = False,
        max_retries: int = 2,
    ) -> str:
        """
        带重试的对话调用

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            temperature: 温度参数
            max_tokens: 最大 token 数
            json_mode: 是否启用 JSON 模式
            max_retries: 最大重试次数

        Returns:
            模型回复文本
        """
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return self.chat(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                )
            except Exception as e:
                last_error = e
                logger.warning(f"LLM 调用失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                if attempt < max_retries:
                    import time
                    time.sleep(1 * (attempt + 1))
        raise last_error

    def get_json_response(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_retries: int = 2,
        max_tokens: int = 4096,
        default: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        获取 JSON 格式响应（带解析和回退）

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            temperature: 温度参数
            max_retries: 最大重试次数
            max_tokens: 最大 token 数
            default: 解析失败时的默认值

        Returns:
            解析后的 JSON 字典
        """
        try:
            raw = self.chat_with_retry(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                json_mode=True,
                max_retries=max_retries,
                max_tokens=max_tokens,
            )
            # 尝试提取 JSON 部分
            raw = raw.strip()
            # 去除可能的 markdown 代码块标记
            if raw.startswith("```"):
                lines = raw.split("\n")
                # 去掉第一行和最后一行 ```
                raw = "\n".join(lines[1:])
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()
            result = json.loads(raw)
            logger.info("JSON 解析成功")
            return result
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"JSON 解析失败: {e}，使用默认值")
            if default is not None:
                return default
            raise


# 全局单例
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取全局 LLM 客户端实例"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
