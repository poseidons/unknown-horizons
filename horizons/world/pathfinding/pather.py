# ###################################################
# Copyright (C) 2009 The Unknown Horizons Team
# team@unknown-horizons.org
# This file is part of Unknown Horizons.
#
# Unknown Horizons is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the
# Free Software Foundation, Inc.,
# 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# ###################################################

import weakref
import sys
import logging

import horizons.main
from horizons.util import Rect, Point
from horizons.world.building.building import Building

from horizons.world.pathfinding import PathBlockedError
from horizons.world.pathfinding.pathfinding import FindPath

"""
In this file, you will find an interface to the pathfinding algorithm.
We just call this interface Pather. It is used by unit to hide implementation details
of the pathfinding algorithm.
"""

class AbstractPather(object):
	"""Interface for pathfinding for use by Unit.
	"""
	log = logging.getLogger("world.pathfinding")
	def __init__(self, unit, move_diagonal, make_target_walkable = True):
		self.move_diagonal = move_diagonal
		self.make_target_walkable = make_target_walkable

		self._unit = weakref.ref(unit)

		self.destination_in_building = False
		self.source_in_building = False

		self.path = None
		self.cur = None

	@property
	def unit(self):
		return self._unit()

	def _get_path_nodes(self):
		"""Returns nodes, where unit can walk on.
		Return value type must be supported by FindPath"""
		raise NotImplementedError

	def _get_blocked_coords(self):
		"""Returns blocked coordinates
		Return value type must be supported by FindPath"""
		return []

	def _check_for_obstacles(self, point):
		"""Check if the path is suddenly blocked by e.g. a unit
		@param point: tuple: (x, y)
		@return: bool, true if path is blocked"""
		return (point in self._get_blocked_coords())

	def calc_path(self, destination, destination_in_building = False, check_only = False):
		"""Calculates a path to destination
		@param destination: a destination supported by pathfinding
		@param destination_in_building: bool, wether destination is in a building.
		                                this makes the unit "enter the building"
		@param check_only: if True the path isn't saved
		@return: False if movement is impossible, else True"""
		source = self.unit.position
		if self.unit.is_moving() and self.path is not None:
			source = Point(*self.path[self.cur])
		else:
			# check if source is in a building
			building = horizons.main.session.world.get_building( \
				self.unit.position.x, self.unit.position.y)
			if building is not None:
				source = building

		path = FindPath()(source, destination, self._get_path_nodes(),
											self._get_blocked_coords(), self.move_diagonal, \
											self.make_target_walkable)

		if path is None:
			return False

		if not check_only:
			self.path = path
			if self.unit.is_moving():
				self.cur = 0
			else:
				self.cur = -1
			self.source_in_building = isinstance(source, Building)
			self.destination_in_building = destination_in_building

		return True

	def revert_path(self, destination_in_building):
		"""Moves back to the source of last movement, using same path"""
		self.cur = -1
		self.destination_in_building = destination_in_building
		self.path.reverse()

	def get_next_step(self):
		"""Returns the next step in the current movement
		@return: Point"""
		self.cur += 1
		if self.path is None or self.cur == len(self.path):
			self.cur = None
			return None

		if self._check_for_obstacles(self.path[self.cur]):
			# path is suddenly blocked, find another path
			self.cur -= 1 # reset, since move is not possible
			if not self.calc_path(Point(*self.path[-1]), self.destination_in_building):
				self.log.info("tile suddenly %s %s blocked for %s %s", \
											self.cur[0], self.cur[1], self.unit, self.unit.getId())
				raise PathBlockedError

		if self.destination_in_building and self.cur == len(self.path)-1:
			self.destination_in_building = False
			self.unit.hide()
		elif self.source_in_building and self.cur == 2:
			self.source_in_building = False
			self.unit.show()

		return Point(*self.path[self.cur])

	def get_move_target(self):
		"""Returns the point where the path leads
		@return: Point or None if no path has been calculated"""
		return None if self.path is None else Point(*self.path[-1])

	def end_move(self):
		"""Pretends that the path is finished in order to make the unit stop"""
		del self.path[self.cur+1:]

	def save(self, db, unitid):
		if self.path is not None:
			for step in xrange(len(self.path)):
				db("INSERT INTO unit_path(`unit`, `index`, `x`, `y`) VALUES(?, ?, ?, ?)", \
					 unitid, step, self.path[step][0], self.path[step][1])

	def load(self, db, worldid):
		"""
		@return: Bool, wether a path was loaded
		"""
		path_steps = db("SELECT x, y FROM unit_path WHERE unit = ? ORDER BY `index`", worldid)
		if len(path_steps) == 0:
			return False
		else:
			self.path = []
			for step in path_steps:
				self.path.append(step) # the sql statement orders the steps
			cur_position = self.unit.position.get_coordinates()[0]
			if cur_position in self.path:
				self.cur = self.path.index(cur_position)
			else:
				self.cur = -1
			return True


class ShipPather(AbstractPather):
	"""Pather for ships (units that move on water tiles)"""
	def __init__(self, unit):
		super(ShipPather, self).__init__(unit, move_diagonal=True)

	def _get_path_nodes(self):
		return horizons.main.session.world.water

	def _get_blocked_coords(self):
		return horizons.main.session.world.ship_map

	def _check_for_obstacles(self, point):
			#check if another ship is blocking the way
			if point in horizons.main.session.world.ship_map and \
				 horizons.main.session.world.ship_map[self.path[self.cur]]() is not self.unit:
				other = horizons.main.session.world.ship_map[self.path[self.cur]]()
				self.log.debug("tile %s %s blocked for %s %s by another ship %s", \
											 point[0], point[1], \
											 self.unit, self.unit.getId(), other)
				return True
			else:
				# also check in super class
				return super(ShipPather, self)._check_for_obstacles(point)

class CollectorPather(AbstractPather):
	"""Pather for collectors, that move freely (without depending on roads)
	such as farm animals."""
	def __init__(self, unit):
		super(CollectorPather, self).__init__(unit, move_diagonal=True)

	def _get_path_nodes(self):
			return self.unit.home_building().path_nodes.nodes

class RoadPather(AbstractPather):
	"""Pather for collectors, that depend on roads (e.g. the one used for the branch office)"""
	def __init__(self, unit):
		super(RoadPather, self).__init__(unit, move_diagonal=False)
		island = horizons.main.session.world.get_island(unit.position.x, unit.position.y)
		self.island = weakref.ref(island)

	def _get_path_nodes(self):
		return self.island().path_nodes.road_nodes

class SoldierPather(AbstractPather):
	"""Pather for units, that move absolutely freely (such as soldiers)"""
	def __init__(self, unit):
		super(SoldierPather, self).__init__(unit, move_diagonal=True, \
																				make_target_walkable=False)

	def _get_path_nodes(self):
		# island might change (e.g. when transported via ship), so reload every time
		island = horizons.main.session.world.get_island(self.unit.position.x, self.unit.position.y)
		return island.path_nodes.nodes

	def _get_blocked_coords(self):
		# TODO
		return []

	def _check_for_obstacles(self, point):
		island = horizons.main.session.world.get_island(self.unit.position.x, self.unit.position.y)
		path_blocked = not island.path_nodes.is_walkable(self.path[self.cur])
		if path_blocked:
			# update list in island, so that new path calculations consider this obstacle
			island.path_nodes.reset_tile_walkability(point)
			self.log.debug("tile %s %s blocked for %s %s on island", point[0], point[1], \
										 self.unit, self.unit.getId());
			return path_blocked
		else:
			# also check in super class
			return super(SoldierPather, self)._check_for_obstacles(point)