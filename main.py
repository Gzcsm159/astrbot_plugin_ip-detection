# main.py
from astrbot.api.all import *
from astrbot.api.event.filter import command, permission_type
import psutil
import socket
import asyncio
from datetime import datetime

@register("ip_monitor", "TechQuery", "IP监控插件", "1.2.0", "https://github.com/yourrepo")
class IPMonitor(Star):
    def init(self, context: Context, config: dict):
        # 初始化配置系统
        super().init(context, config)
        self.context = context
        self.config = config  # 关键修正点：显式保存配置
        self.last_ips = {"v4": set(), "v6": set()}
        self.monitor_task = None
        self._init_monitor()

    def _init_monitor(self):
        """安全启动监控任务"""
        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
        self.monitor_task = asyncio.create_task(self._safe_monitor())

    def _get_network_ips(self):
        """获取有效IP地址（增强过滤逻辑）"""
        ip_info = {"v4": set(), "v6": set()}
        for iface, addrs in psutil.net_if_addrs().items():
            # 过滤虚拟网络接口
            if any(keyword in iface.lower() for keyword in ["virtual", "vmware", "vEthernet"]):
                continue
            
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    if not addr.address.startswith('127.') and addr.netmask != '255.255.255.255':
                        ip_info["v4"].add(addr.address)
                elif addr.family == socket.AF_INET6:
                    clean_addr = addr.address.split('%')[0]
                    if not clean_addr.startswith(('fe80', '::1')) and not clean_addr.endswith('1'):
                        ip_info["v6"].add(clean_addr)
        return ip_info

    async def _safe_monitor(self):
        """带错误恢复的监控循环"""
        while True:
            try:
                await self._monitor_loop()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[MONITOR ERROR] {str(e)}")
                await asyncio.sleep(60)

    async def _monitor_loop(self):
        """监控主循环（精确到秒级检测）"""
        await asyncio.sleep(10)  # 初始延迟
        
        while True:
            current_ips = self._get_network_ips()
            changes = self._detect_changes(current_ips)
            
            if changes and self.config.get("notify_target"):
                await self._send_alert(changes)
                self.last_ips = current_ips
                
            await asyncio.sleep(300)  # 5分钟检测间隔

    def _detect_changes(self, current_ips):
        """精确变化检测"""
        changes = {}
        for ip_type in ["v4", "v6"]:
            old_ips = self.last_ips.get(ip_type, set())
            new_ips = current_ips.get(ip_type, set())
            
            added = new_ips - old_ips
            removed = old_ips - new_ips
            
            if added or removed:
                changes[ip_type] = {
                    "added": sorted(added),
                    "removed": sorted(removed)
                }
        return changes

    async def _send_alert(self, changes):
        """增强通知功能"""
        msg = (MessageChain()
            .message("🌐 网络地址变动告警\n")
            .text(f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"))
        
        for ip_type, diff in changes.items():
            version = "IPv4" if ip_type == "v4" else "IPv6"
            msg.message(f"【{version}】\n")
            if diff["added"]:
                msg.message(f"➕ 新增: {', '.join(diff['added'])}\n")
            if diff["removed"]:
                msg.message(f"➖ 移除: {', '.join(diff['removed'])}\n")
        
        try:
            # 添加平台适配消息组件
            if "qq" in self.config.get("notify_target", ""):
                msg = msg.face(112)  # 添加QQ微笑表情
            
            await self.context.send_message(
                unified_msg_origin=self.config["notify_target"],
                message=msg
            )
        except Exception as e:
            print(f"[NOTIFICATION FAILED] {str(e)}")

    @command("set_notify")
    @permission_type("admin")
    async def set_notify_channel(self, event: AstrMessageEvent):
        """配置通知频道（带验证机制）"""
        # 确保配置键存在
        if "notify_target" not in self.config:
            self.config["notify_target"] = ""
        
        # 保存配置
        self.config["notify_target"] = event.unified_msg_origin
        self.context.config_manager.save_config(self.name, self.config)  # 显式保存
        
        # 构建响应消息
        platform = event.get_platform_name().upper()
        target_type = "群组" if event.is_group_message() else "私聊"
        target_id = event.get_group_id() or event.get_sender_id()
        
        response = (MessageChain()
            .message("✅ 通知设置更新成功\n")
            .message(f"▪ 平台: {platform}\n")
            .message(f"▪ 类型: {target_type}\n")
            .message(f"▪ ID: {target_id}"))
        
        yield response

    @command("netstat")
    async def get_network_status(self, event: AstrMessageEvent):
        """实时网络状态查询"""
        ips = self._get_network_ips()
        stats = (MessageChain()
            .message("📊 实时网络监控\n")
            .message(f"🖥 IPv4: {', '.join(ips['v4']) or '无'}\n")
            .message(f"🌐 IPv6: {', '.join(ips['v6']) or '无'}\n")
            .message(f"⏱ 检测时间: {datetime.now().strftime('%H:%M:%S')}"))
        
        yield stats

    @command("monitor")
    @permission_type("admin")
    async def control_monitor(self, event: AstrMessageEvent, action: str = "status"):
        """监控任务管理（增强版）"""
        action = action.lower()
        status_map = {
            True: "✅ 运行中",
            False: "🛑 已停止"
        }
        
        if action == "stop":
            if self.monitor_task and not self.monitor_task.done():
                self.monitor_task.cancel()
                yield event.plain_result("监控任务已停止")
            else:
                yield event.plain_result("监控任务未运行")
        elif action == "start":
            self._init_monitor()
            yield event.plain_result("监控任务已启动")
        elif action == "restart":
            self._init_monitor()
            yield event.plain_result("监控任务已重启")
        else:
            current_status = self.monitor_task and not self.monitor_task.done()
            yield event.plain_result(f"监控状态：{status_map[current_status]}")
