from astrbot.api.all import *
from astrbot.api.event.filter import (
    command,
    permission_type,
    PermissionType,
    EventMessageType
)
from astrbot.api.message_components import Plain, MessageChain
import psutil
import socket
import asyncio
from datetime import datetime

@register("ip_monitor", "YourName", "IP地址监控插件", "1.0.0", "https://your.repo.url")
class IPMonitor(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.last_ipv4 = []
        self.last_ipv6 = []
        self.notify_target = None
        asyncio.create_task(self.ip_change_monitor())

    def _get_network_ips(self):
        addrs = psutil.net_if_addrs()
        ipv4_list = []
        ipv6_list = []
        
        for iface, snics in addrs.items():
            for snic in snics:
                if snic.family == socket.AF_INET and snic.address != '127.0.0.1':
                    ipv4_list.append(snic.address)
                elif snic.family == socket.AF_INET6:
                    addr = snic.address.split('%')[0]
                    if addr != '::1':
                        ipv6_list.append(addr)
        return sorted(ipv4_list), sorted(ipv6_list)

    async def ip_change_monitor(self):
        await asyncio.sleep(10)
        
        while True:
            try:
                current_v4, current_v6 = self._get_network_ips()
                
                v4_changed = current_v4 != self.last_ipv4
                v6_changed = current_v6 != self.last_ipv6
                
                if (v4_changed or v6_changed) and self.notify_target:
                    message = MessageChain([
                        Plain("🛜 检测到IP地址变化\n"),
                        Plain(f"IPv4: {', '.join(self.last_ipv4) or '无'} → {', '.join(current_v4)}\n") if v4_changed else None,
                        Plain(f"IPv6: {', '.join(self.last_ipv6) or '无'} → {', '.join(current_v6)}\n") if v6_changed else None,
                        Plain(f"⏰ 检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    ]).filter()  # 过滤None值
                    
                    await self.context.send_message(
                        unified_msg_origin=self.notify_target,
                        message=message
                    )
                    
                    self.last_ipv4 = current_v4
                    self.last_ipv6 = current_v6
                
                elif not self.last_ipv4:
                    self.last_ipv4 = current_v4
                    self.last_ipv6 = current_v6
                
                await asyncio.sleep(600)
                
            except Exception as e:
                print(f"[IP监控] 任务出错: {str(e)}")
                await asyncio.sleep(60)

    @command("set_notify")
    @permission_type(PermissionType.ADMIN)
    async def set_notify_channel(self, event: AstrMessageEvent):
        self.notify_target = event.unified_msg_origin
        
        # 使用正确的消息构建方式
        response = event.make_result().message(
            MessageChain([
                Plain("✅ 通知频道设置成功！\n"),
                Plain(f"群组ID: {event.get_group_id()}\n") if event.get_message_type() == EventMessageType.GROUP_MESSAGE 
                else Plain(f"用户ID: {event.get_sender_id()}\n"),
                Plain(f"平台类型: {event.get_platform_name()}")
            ])
        )
        
        yield response

    @command("sysinfo")
    async def get_system_info(self, event: AstrMessageEvent):
        current_v4, current_v6 = self._get_network_ips()
        
        info = event.make_result().message(
            MessageChain([
                Plain("🖥️ 系统状态监控\n"),
                Plain(f"IPv4: {', '.join(current_v4) or '无'}\n"),
                Plain(f"IPv6: {', '.join(current_v6) or '无'}\n"),
                Plain(f"CPU使用率: {psutil.cpu_percent(interval=1)}%\n"),
                Plain(f"内存使用: {psutil.virtual_memory().percent}%\n"),
                Plain(f"磁盘使用: {psutil.disk_usage('/').percent}%"),
                Plain("\n\n🔔 通知频道: 已启用" if self.notify_target else "\n\n🔕 通知频道: 未设置")
            ])
        )

        yield info

    @command("test_notify")
    @permission_type(PermissionType.ADMIN)
    async def test_notification(self, event: AstrMessageEvent):
        if not self.notify_target:
            yield event.plain_result("❌ 尚未设置通知频道")
            return
        
        try:
            await self.context.send_message(
                unified_msg_origin=self.notify_target,
                message=MessageChain([
                    Plain("🔔 测试通知\n"),
                    Plain("✅ 通知系统工作正常！")
                ])
            )
            yield event.plain_result("测试通知已发送")
        except Exception as e:
            yield event.plain_result(f"❌ 通知发送失败: {str(e)}")
