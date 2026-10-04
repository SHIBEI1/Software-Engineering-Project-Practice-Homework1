"""用于演示代码解释 Agent 的简单示例。"""


def sort_unique(numbers: list[int]) -> list[int]:
    """返回去重后的升序整数列表。"""
    if not all(isinstance(item, int) for item in numbers):
        raise TypeError("numbers 必须全部是整数")
    return sorted(set(numbers))


def main() -> None:
    values = [5, 3, 5, 1, 3]
    print(sort_unique(values))


if __name__ == "__main__":
    main()
