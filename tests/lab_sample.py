"""The approved laboratory style sample, shared by pipeline previews."""

SAMPLE = '''     清衣，布丁不是自己消失的。别急着甩锅给世界线，我先把调查结果整理给你。

# 冰箱里的布丁去哪了？

**结论：先核对事实，再决定找谁赔。** 查看聊天记录，并用 `inspect_fridge()` 记录库存。

> **调查原则**
>
> 一段聊天记录不等于完整证据。不要把猜测当结论。
> > 补充：回看消息时，保留上下文。

## 调查进度

- [x] 确认布丁失踪
- [ ] 找到真正的食用者

| 线索 | 可信度 | 下一步 |
| --- | --- | --- |
| 空包装 | 较高 | 核对时间 |
| 口头解释 | 待验证 | 对照记录 |

## 技术附件

```python
def inspect_fridge(count):
    if count == 0:
        return "布丁不在了，问题还在。"
```
'''
