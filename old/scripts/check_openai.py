import os
import sys
from openai import OpenAI
from dotenv import load_dotenv


def main():
    load_dotenv()
    base_url = os.getenv("OPENAI_BASE_URL")
    timeout = float(os.getenv("OPENAI_TIMEOUT_SEC", "20"))
    print(f"OPENAI_BASE_URL={base_url or '(default)'}")
    print(f"OPENAI_TIMEOUT_SEC={timeout}")

    try:
        client = OpenAI(base_url=base_url, timeout=timeout) if base_url else OpenAI(timeout=timeout)
    except Exception as e:
        print(f"[INIT ERROR] {e}")
        sys.exit(1)

    try:
        resp = client.responses.create(
            model=os.getenv("OPENAI_VISION_MODEL", "gpt-4o"),
            input=[{"role": "user", "content": "ping"}]
        )
        print("[OK] responses.create succeeded")
        text = getattr(resp, "output_text", "")
        print(f"[OUTPUT] {text[:200]}")
        sys.exit(0)
    except Exception as e:
        print(f"[REQUEST ERROR] {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
