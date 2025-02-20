from astrbot.api.all import *
from astrbot.api.event.filter import command, permission_type, PermissionType
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
        self.notify_target = None  # 存储完整事件对象
        asyncio.create_task(self.ip_change_monitor())

    def _get_network_ips(self):
        """获取当前所有网络接口IP"""
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
        """IP变化监控后台任务"""
        await asyncio.sleep(10)
        
        while True:
            try:
                current_v4, current_v6 = self._get_network_ips()
                
                v4_changed = current_v4 != self.last_ipv4
                v6_changed = current_v6 != self.last_ipv6
                
                if (v4_changed or v6_changed) and self.notify_target:
                    msg_parts = [
                        Plain("🛜 检测到IP地址变化\n"),
                        Plain(f"IPv4: {', '.join(self.last_ipv4) or '无'} → {', '.join(current_v4)}\n") if v4_changed else None,
                        Plain(f"IPv6: {', '.join(self.last_ipv6) or '无'} → {', '.join(current_v6)}\n") if v6_changed else None,
                        Plain(f"⏰ 检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    ]
                    
                    # 过滤空内容
                    msg_parts = [p for p in msg_parts if p]
                    
                    await self.context.send_message(
                        target_origin=self.notify_target["origin"],
                        message=msg_parts
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
        """设置通知频道"""
        # 存储完整事件信息
        self.notify_target = {
            "origin": event.origin_dict,  # 使用原始事件数据
            "chat_type": event.message_type.value
        }
        
        # 构建响应消息
        response = [
            Plain("✅ 通知频道设置成功！"),
            Plain(f"\n聊天类型: {event.message_type.name}")
        ]
        
        if hasattr(event, 'group_id'):
            response.append(Plain(f"\n群组ID: {event.group_id}"))
        elif hasattr(event, 'user_id'):
            response.append(Plain(f"\n用户ID: {event.user_id}"))

        yield response  # 直接返回消息部件列表

    @command("sysinfo")
    async def get_system_info(self, event: AstrMessageEvent):
        """获取系统信息"""
        current_v4, current_v6 = self._get_network_ips()
        
        cpu_usage = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        info_parts = [
            Plain("🖥️ 系统状态监控\n"),
            Plain(f"IPv4: {', '.join(current_v4) or '无'}\n"),
            Plain(f"IPv6: {', '.join(current_v6) or '无'}\n"),
            Plain(f"CPU使用率: {cpu_usage}%\n"),
            Plain(f"内存使用: {mem.percent}%\n"),
            Plain(f"磁盘使用: {disk.percent}%")
        ]
        
        if self.notify_target:
            info_parts.append(Plain("\n\n🔔 通知频道: 已启用"))
        else:
            info_parts.append(Plain("\n\n🔕 通知频道: 未设置"))

        yield info_parts  # 直接返回消息部件列表

    @command("test_notify")
    @permission_type(PermissionType.ADMIN)
    async def test_notification(self, event: AstrMessageEvent):
        """测试通知"""
        if not self.notify_target:
            yield [Plain("❌ 尚未设置通知频道")]
            return
        
        try:
            await self.context.send_message(
                target_origin=self.notify_target["origin"],
                message=[
                    Plain("🔔 测试通知\n"),
                    Plain("✅ 通知系统工作正常！")
                ]
            )
            yield [Plain("测试通知已发送")]
        except Exception as e:
            yield [Plain(f"❌ 通知发送失败: {str(e)}")]
