import asyncio
from typing import Callable, Dict, List, Any


class Dispatcher:
    """一个简单的异步事件分发器（同步注册、异步触发）

    示例：
        dispatcher = Dispatcher()

        async def on_click(interaction):
            await interaction.response.send_message("按钮被点击！")

        dispatcher.on("button_clicked", on_click)
        await dispatcher.emit("button_clicked", interaction)
    """

    def __init__(self):
        # 存储监听函数列表：{ event_name: [callback1, callback2, ...] }
        self._listeners: Dict[str, List[Callable[..., Any]]] = {}

    # 同步注册事件
    def on(self, event_name: str, callback: Callable[..., Any]) -> None:
        """注册事件监听函数"""
        self._listeners.setdefault(event_name, []).append(callback)

    # 同步注销事件
    def off(self, event_name: str, callback: Callable[..., Any]) -> None:
        """移除指定事件的监听函数"""
        if event_name in self._listeners:
            self._listeners[event_name] = [
                cb for cb in self._listeners[event_name] if cb != callback
            ]
            if not self._listeners[event_name]:
                del self._listeners[event_name]

    # 异步触发事件
    async def emit(self, event_name: str, *args, **kwargs) -> None:
        """触发事件，依次执行所有监听函数"""
        listeners = list(self._listeners.get(event_name, []))  # 复制一份，防止迭代中修改
        if not listeners:
            return

        # 逐个执行回调（若是异步函数则 await）
        for callback in listeners:
            try:
                result = callback(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                # 不让一个监听器异常影响其他监听器
                print(f"[Dispatcher] Error in listener for '{event_name}': {e}")
