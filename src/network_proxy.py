import logging
from typing import Dict, Any, Optional

from quarry.net.proxy import Bridge, DownstreamFactory
from quarry.types.buffer import Buffer
from twisted.internet import reactor

from src.scheduler import StateContext, PriorityScheduler, SwingInterruptionMatrix

logger = logging.getLogger("mc_auto.network_proxy")

class SnifferBridge(Bridge):
    """Bridge protocol intercepting packets between the client and remote server."""

    def packet_upstream_set_slot(self, buff: Buffer) -> None:
        """Handles slot updates sent from server to client (upstream -> downstream)."""
        buff.save()
        try:
            window_id = buff.unpack('b')
            state_id = buff.unpack_varint()
            slot_id = buff.unpack('h')
            item = buff.unpack_slot()

            # Window ID 0 is the player's main inventory/hotbar
            # Slot indices 36-44 correspond to hotbar slots 0-8
            expected_slot = 36 + self.factory.context.active_slot

            if window_id == 0 and slot_id == expected_slot:
                logger.debug(f"Intercepted set_slot for active slot {expected_slot}")
                if item is None or item.get('item') is None:
                    # Slot is empty
                    self.factory.context.current_durability = 0
                    self.factory.context.equipped_tool_multiplier = 1.0
                else:
                    item_id = item['item']
                    item_data = self.factory.item_lookup.get(item_id)
                    
                    if item_data:
                        name = item_data.get('name', '')
                        max_durability = item_data.get('maxDurability', 0)
                        
                        damage = 0
                        nbt = item.get('nbt')
                        if nbt and 'Damage' in nbt:
                            # NBT fields in quarry are tag objects
                            damage = getattr(nbt['Damage'], 'value', 0)

                        if max_durability > 0:
                            self.factory.context.current_durability = max_durability - damage
                        else:
                            self.factory.context.current_durability = 0
                            
                        self.factory.context.equipped_tool_multiplier = self.factory.get_tool_multiplier(name)
                        logger.info(f"Updated equipped item '{name}' | Durability: {self.factory.context.current_durability} | Multiplier: {self.factory.context.equipped_tool_multiplier}")
                    else:
                        # Unknown item ID
                        self.factory.context.current_durability = 0
                        self.factory.context.equipped_tool_multiplier = 1.0

                # Release the scheduler block
                self.factory.context.slot_confirmed = True
                self.factory.context.action_lock.set()

        except Exception as e:
            logger.error(f"Failed to parse packet_upstream_set_slot: {e}", exc_info=True)
        finally:
            buff.restore()
            self.downstream.send_packet("set_slot", buff.read())

    def packet_downstream_held_item_change(self, buff: Buffer) -> None:
        """Handles hotbar slot changes requested by the local client (downstream -> upstream)."""
        buff.save()
        try:
            slot_id = buff.unpack('h')
            if 0 <= slot_id <= 8:
                self.factory.interruption_matrix.handle_slot_change(self.factory.context.active_slot, slot_id)
                self.factory.context.active_slot = slot_id
                logger.info(f"Client requested slot change to: {slot_id}. Actions locked.")
        except Exception as e:
            logger.error(f"Failed to parse packet_downstream_held_item_change: {e}", exc_info=True)
        finally:
            buff.restore()
            self.upstream.send_packet("held_item_change", buff.read())

    def packet_upstream_held_item_change(self, buff: Buffer) -> None:
        """Handles server-forced held item shifts (upstream -> downstream)."""
        buff.save()
        try:
            slot_id = buff.unpack('b')
            if 0 <= slot_id <= 8:
                self.factory.context.active_slot = slot_id
                self.factory.context.slot_confirmed = True
                self.factory.context.action_lock.set()
                logger.info(f"Server confirmed forced slot change to: {slot_id}. Actions unlocked.")
        except Exception as e:
            logger.error(f"Failed to parse packet_upstream_held_item_change: {e}", exc_info=True)
        finally:
            buff.restore()
            self.downstream.send_packet("held_item_change", buff.read())

    def packet_downstream_position(self, buff: Buffer) -> None:
        """Handles client position updates (downstream -> upstream)."""
        buff.save()
        try:
            x = buff.unpack('d')
            y = buff.unpack('d')
            z = buff.unpack('d')
            self.factory.update_player_position(x, y, z, source="client")
        except Exception as e:
            logger.error(f"Failed to parse packet_downstream_position: {e}", exc_info=True)
        finally:
            buff.restore()
            self.upstream.send_packet("position", buff.read())

    def packet_downstream_position_and_look(self, buff: Buffer) -> None:
        """Handles client position and rotation updates (downstream -> upstream)."""
        buff.save()
        try:
            x = buff.unpack('d')
            y = buff.unpack('d')
            z = buff.unpack('d')
            self.factory.update_player_position(x, y, z, source="client")
        except Exception as e:
            logger.error(f"Failed to parse packet_downstream_position_and_look: {e}", exc_info=True)
        finally:
            buff.restore()
            self.upstream.send_packet("position_and_look", buff.read())

    def packet_upstream_player_position_and_look(self, buff: Buffer) -> None:
        """Handles server-authoritative position packets (upstream -> downstream)."""
        buff.save()
        try:
            x = buff.unpack('d')
            y = buff.unpack('d')
            z = buff.unpack('d')
            self.factory.update_player_position(x, y, z, source="server")
        except Exception as e:
            logger.error(f"Failed to parse packet_upstream_player_position_and_look: {e}", exc_info=True)
        finally:
            buff.restore()
            self.downstream.send_packet("player_position_and_look", buff.read())


class SnifferDownstreamFactory(DownstreamFactory):
    """Factory handling incoming client connections and proxying network streams."""
    bridge_class = SnifferBridge

    def __init__(self, context: StateContext, scheduler: PriorityScheduler, item_lookup: Dict[int, Any], *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.context: StateContext = context
        self.scheduler: PriorityScheduler = scheduler
        self.item_lookup: Dict[int, Any] = item_lookup
        self.interruption_matrix: SwingInterruptionMatrix = SwingInterruptionMatrix(context)
        
        # Autorun position state registers
        self.server_x: float = 0.0
        self.server_y: float = 0.0
        self.server_z: float = 0.0

    def update_player_position(self, x: float, y: float, z: float, source: str) -> None:
        """Synchronizes coordinate offsets and monitors drift limits to prevent packet drops."""
        if source == "server":
            self.server_x = x
            self.server_y = y
            self.server_z = z
            
            # Initially sync context if unset
            if self.context.player_x == 0.0 and self.context.player_y == 0.0 and self.context.player_z == 0.0:
                self.context.player_x = x
                self.context.player_y = y
                self.context.player_z = z
        elif source == "client":
            self.context.player_x = x
            self.context.player_y = y
            self.context.player_z = z
            
            # Check for desync/drift against server position
            if self.server_x != 0.0:
                drift = ((x - self.server_x)**2 + (y - self.server_y)**2 + (z - self.server_z)**2)**0.5
                if drift > 0.5:
                    logger.warning(f"Position desync exceeding 0.5 blocks detected (drift={drift:.4f}). Halting scheduler loops.")
                    self.context.swing_interrupted = True
                    self.context.slot_confirmed = False
                    self.context.action_lock.clear()

    def get_tool_multiplier(self, tool_name: str) -> float:
        """Retrieves raw swing speed multipliers matching target tool tier classifications."""
        if not tool_name:
            return 1.0
            
        name = tool_name.lower()
        if "pickaxe" in name or "shovel" in name or "axe" in name or "hoe" in name:
            if "netherite" in name:
                return 9.0
            elif "diamond" in name:
                return 8.0
            elif "iron" in name:
                return 6.0
            elif "stone" in name:
                return 4.0
            elif "gold" in name:
                return 12.0
            elif "wood" in name or "wooden" in name:
                return 2.0
        elif "shears" in name:
            return 1.5
            
        return 1.0
