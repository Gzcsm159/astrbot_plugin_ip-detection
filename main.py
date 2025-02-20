# -*- coding: utf-8 -*-
from astrbot.api.all import *  # 导入框架核心功能
from astrbot.api.event.filter import (  # 事件过滤器相关
    command,
    permission_type,
    PermissionType,
    EventMessageType
)
from astrbot.api.message_components import Plain  # 消息组件
import psutil       # 系统监控库
import socket       # 网络信息获取
import asyncio      # 异步支持
from datetime import datetime  # 时间处理

@register("ip_monitor", "YourName", "IP监控插件", "1.0.0", "https://your.repo.url")
class IPMonitor(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 初始化存储变量
        self.last_ipv4 = []    # 上次记录的IPv4地址
        self.last_ipv6 = []    # 上次记录的IPv6地址
        self.notify_target = None  # 通知目标标识
        # 启动后台监控任务
        asyncio.create_task(self.ip_change_monitor())

    def _get_network_ips(self):
        """获取当前所有网络接口的有效IP地址"""
        addrs = psutil.net_if_addrs()
        ipv4_list = []
        ipv6_list = []
        
        # 遍历网络接口
        for iface, snics in addrs.items():
            for snic in snics:
                # 过滤IPv4地址（排除本地回环）
                if snic.family == socket.AF_INET and snic.address != '127.0.0.1':
                    ipv4_list.append(snic.address)
                # 过滤IPv6地址（排除本地回环）
                elif snic.family == socket.AF_INET6:
                    addr = snic.address.split('%')[0]
                    if addr != '::1':
                        ipv6_list.append(addr)
        return sorted(ipv4_list), sorted(ipv6_list)

    async def ip_change_monitor(self):
        """IP变化监控后台任务"""
        await asyncio.sleep(10)  # 初始延迟10秒
        
        while True:
            try:
                # 获取当前IP地址
                current_v4, current_v6 = self._get_network_ips()
                
                # 检测变化
                v4_changed = current_v4 != self.last_ipv4
                v6_changed = current_v6 != self.last_ipv6
                
                # 如果检测到变化且有设置通知目标
                if (v4_changed or v6_changed) and self.notify_target:
                    # 构建消息链
                    message = MessageChain()
                    message.append(Plain("🛜 检测到IP地址变化\n"))
                    
                    if v4_changed:
                        old_v4 = ', '.join(self.last_ipv4) or '无'
                        new_v4 = ', '.join(current_v4)
                        message.append(Plain(f"IPv4: {old_v4} → {new_v4}\n"))
                    
                    if v6_changed:
                        old_v6 = ', '.join(self.last_ipv6) or '无'
                        new_v6 = ', '.join(current_v6)
                        message.append(Plain(f"IPv6: {old_v6} → {new_v6}\n"))
                    
                    # 添加时间戳
                    message.append(Plain(f"⏰ 检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"))
                    
                    # 发送通知
                    await self.context.send_message(
                        unified_msg_origin=self.notify_target,
                        message=message
                    )
                    
                    # 更新记录
                    self.last_ipv4 = current_v4
                    self.last_ipv6 = current_v6
                
                # 首次运行初始化
                elif not self.last_ipv4:
                    self.last_ipv4 = current_v4
                    self.last_ipv6 = current_v6
                
                await asyncio.sleep(600)  # 每10分钟检查一次
                
            except Exception as e:
                print(f"[IP监控] 任务出错: {str(e)}")
                await asyncio.sleep(60)  # 出错后等待1分钟

    @command("set_notify")
    @permission_type(PermissionType.ADMIN)
    async def set_notify_channel(self, event: AstrMessageEvent):
        """设置通知频道（仅管理员可用）"""
        # 存储消息来源标识
        self.notify_target = event.unified_msg_origin
        
        # 构建响应消息
        response = event.make_result()
        response.append(Plain("✅ 通知频道设置成功！\n"))
        
        # 判断消息类型
        if event.get_message_type() == EventMessageType.GROUP_MESSAGE:
            response.append(Plain(f"群组ID: {event.get_group_id()}\n"))
        else:
            response.append(Plain(f"用户ID: {event.get_sender_id()}\n"))
        
        response.append(Plain(f"平台类型: {event.get_platform_name()}"))
        
        yield response

    @command("sysinfo")
    async def get_system_info(self, event: AstrMessageEvent):
        """获取系统状态信息"""
        current_v4, current_v6 = self._get_network_ips()
        
        # 获取系统指标
        cpu_usage = psutil.cpu_percent(interval=1)  # CPU使用率
        mem = psutil.virtual_memory()               # 内存使用
        disk = psutil.disk_usage('/')               # 磁盘使用
        
        # 构建消息
        info = event.make_result()
        info.append(Plain("🖥️ 系统状态监控\n"))
        info.append(Plain(f"IPv4: {', '.join(current_v4) or '无'}\n"))
        info.append(Plain(f"IPv6: {', '.join(current_v6) or '无'}\n"))
        info.append(Plain(f"CPU使用率: {cpu_usage}%\n"))
        info.append(Plain(f"内存使用: {mem.percent}%\n"))
        info.append(Plain(f"磁盘使用: {disk.percent}%"))
        
        # 添加通知状态
        if self.notify_target:
            info.append(Plain("\n\n🔔 通知频道: 已启用"))
        else:
            info.append(Plain("\n\n🔕 通知频道: 未设置"))

        yield info

    @command("test_notify")
    @permission_type(PermissionType.ADMIN)
    async def test_notification(self, event: AstrMessageEvent):
        """测试通知功能（仅管理员可用）"""
        if not self.notify_target:
            yield event.plain_result("❌ 尚未设置通知频道")
            return
        
        try:
            # 构建测试消息
            test_msg = MessageChain()
            test_msg.append(Plain("🔔 测试通知\n"))
            test_msg.append(Plain("✅ 通知系统工作正常！"))
            
            # 发送通知
            await self.context.send_message(
                unified_msg_origin=self.notify_target,
                message=test_msg
            )
            yield event.plain_result("测试通知已发送")
        except Exception as e:
            yield event.plain_result(f"❌ 通知发送失败: {str(e)}")
