import re
import os

def get_log_totals(log_path="chapters/character_log.qmd"):
    if not os.path.exists(log_path):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_path = os.path.join(base_dir, "chapters", "character_log.qmd")
        
    with open(log_path, "r", encoding="utf-8") as f:
        content = f.read()

    env = {}

    # 1. Execute top-level ```{python} ... ``` code blocks
    block_pattern = re.compile(r'```\{python\}(.*?)```', re.DOTALL)
    for block in block_pattern.findall(content):
        clean_lines = [line for line in block.splitlines() if not line.strip().startswith('#|')]
        exec("\n".join(clean_lines), env)

    # 2. Execute inline `{python} ...` expressions in chronological order
    inline_pattern = re.compile(r'`\{python\}\s*(.*?)`')
    for expr in inline_pattern.findall(content):
        try:
            eval(expr, env)
        except Exception:
            try:
                exec(expr, env)
            except Exception as e:
                print(f"Warning: Failed to evaluate inline python expression '{expr}': {e}")

    return {
        "Karma": env.get("Karma", 0),
        "Lifetime_Karma": env.get("Lifetime_Karma", 0),
        "Nuyen": env.get("Nuyen", 0),
        "Initiation_Grade": env.get("Initiation_Grade", 0),
    }

if __name__ == "__main__":
    totals = get_log_totals()
    print("Log Totals:", totals)
