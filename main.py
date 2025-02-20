# 导入所有必要组件（符合教程推荐方式）
from astrbot.api.all import *
import psutil
import socket
import asyncio
from datetime import datetime

@register("sysinfo_monitor", "YourName", "系统监控插件", "1.0.0", "https://your.repo.url")
class SysMonitor(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 初始化存储数据
        self.last_ipv4 = []      # 存储上次检测的IPv4地址
        self.last_ipv6 = []      # 存储上次检测的IPv6地址
        self.notify_chat = None  # 存储通知频道信息
        # 启动后台检测任务
        asyncio.create_task(self.ip_monitor())

    def _get_ips(self):
        """获取当前所有有效IP地址（带排序）"""
        addrs = psutil.net_if_addrs()
        ipv4 = []
        ipv6 = []
        
        for interface, snics in addrs.items():
            for snic in snics:
                # 处理IPv4地址
                if snic.family == socket.AF_INET and snic.address != '127.0.0.1':
                    ipv4.append(snic.address)
                # 处理IPv6地址
                elif snic.family == socket.AF_INET6:
                    address = snic.address.split('%')[0]
                    if address != '::1':
                        ipv6.append(address)
        return sorted(ipv4), sorted(ipv6)

    async def ip_monitor(self):
        """IP地址变化监控任务"""
        await asyncio.sleep(10)  # 初始延迟等待系统就绪
        
        while True:
            try:
                current_ipv4, current_ipv6 = self._get_ips()
                
                # 检测变化
                ipv4_changed = current_ipv4 != self.last_ipv4
                ipv6_changed = current_ipv6 != self.last_ipv6
                
                # 如果检测到变化且有设置通知频道
                if (ipv4_changed or ipv6_changed) and self.notify_chat:
                    # 构建消息链
                    message = MessageChain()
                    message.append(Plain("🛜 检测到IP地址变化：\n"))
                    
                    if ipv4_changed:
                        message.append(Plain(f"IPv4: {', '.join(self.last_ipv4) or '无'} → {', '.join(current_ipv4)}\n"))
                    if ipv6_changed:
                        message.append(Plain(f"IPv6: {', '.join(self.last_ipv6) or '无'} → {', '.join(current_ipv6)}\n"))
                    
                    message.append(Plain(f"\n⌚ 检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"))
                    
                    # 发送通知
                    await self.context.send_message(
                        unified_msg_origin=self.notify_chat["origin"],
                        chain=message
                    )
                    
                    # 更新记录
                    self.last_ipv4 = current_ipv4
                    self.last_ipv6 = current_ipv6
                
                # 首次运行初始化
                elif not self.last_ipv4:
                    self.last_ipv4 = current_ipv4
                    self.last_ipv6 = current_ipv6
                
                await asyncio.sleep(600)  # 10分钟检测间隔
                
            except Exception as e:
                print(f"监控任务出错: {str(e)}")
                await asyncio.sleep(60)  # 出错后等待1分钟

    @command("set_notify")
    @permission_type(PermissionType.ADMIN)
    async def set_notify_channel(self, event: AstrMessageEvent):
        """设置通知频道（管理员命令）"""
        # 存储频道信息（符合教程的unified_msg_origin规范）
        self.notify_chat = {
            "origin": event.unified_msg_origin,
            "chat_id": event.chat_id
        }
        
        # 构建确认消息
        confirm_msg = MessageChain()
        confirm_msg.append(Plain("✅ 通知频道设置成功！\n"))
        confirm_msg.append(Plain(f"频道ID: {event.chat_id}"))
        
        # 发送确认消息
        yield event.chain_result(confirm_msg)

    @command("sysinfo")
    async def get_sysinfo(self, event: AstrMessageEvent):
        """获取当前系统信息"""
        # 获取IP信息
        current_ipv4, current_ipv6 = self._get_ips()
        
        # 获取系统指标
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # 构建消息链
        info_msg = MessageChain()
        info_msg.append(Plain("🖥️ 系统状态报告\n"))
        info_msg.append(Plain(f"IPv4地址: {', '.join(current_ipv4) or '无'}\n"))
        info_msg.append(Plain(f"IPv6地址: {', '.join(current_ipv6) or '无'}\n"))
        info_msg.append(Plain(f"CPU使用率: {cpu_usage}%\n"))
        info_msg.append(Plain(f"内存使用: {memory.percent}%\n"))
        info_msg.append(Plain(f"磁盘使用: {disk.percent}%"))
        
        # 添加通知频道信息
        if self.notify_chat:
            info_msg.append(Plain("\n\n🔔 通知频道: 已设置"))
        else:
            info_msg.append(Plain("\n\n🔕 通知频道: 未设置"))

        yield event.chain_result(info_msg)

    @command("test_notify")
    @permission_type(PermissionType.ADMIN)
    async def test_notify(self, event: AstrMessageEvent):
        """测试通知功能"""
        if not self.notify_chat:
            yield event.plain_result("❌ 尚未设置通知频道")
            return
        
        test_msg = MessageChain()
        test_msg.append(Plain("🔔 这是一个测试通知\n"))
        test_msg.append(Plain("✅ 通知功能正常！"))
        
        # 发送测试通知
        await self.context.send_message(
            unified_msg_origin=self.notify_chat["origin"],
            chain=test_msg
        )
        
        yield event.plain_result("测试通知已发送")
