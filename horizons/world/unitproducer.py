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


from production import SecondaryProducer
from horizons.util.point import Point
from horizons.command.unit import CreateUnit

class UnitProducer(SecondaryProducer):

	def __init__(self, **kwargs):
		super(UnitProducer, self).__init__(**kwargs)
		self.output_point = None
		self._init()

	def _init(self):
		# Make sure the unitproducer can't store to many resources
		self.inventory.limit = 6
		# production_queue holds the ids of the production_lines
		# currently waiting for construction.
		self.production_queue = []

		# Load production lines
		self.production = {}
		for (id,) in horizons.main.db("SELECT rowid FROM data.production_line where %(type)s = ?"\
								  % {'type' : 'building' if self.object_type == 0 else 'unit'}, self.id):
			self.production[id] = UnitProductionLine(id)

		# Set production line to None, we don't produce automatically
		self.active_production_line = None
		self.active = False

		if isinstance(self, Building):
			self.toggle_costs()  # needed to get toggle to the right position


	def production_step(self):
		if horizons.main.debug:
			print "UnitProducer production_step", self.getId()
		if sum(self.__used_resources.values()) >= -sum(p for p in self.production[self.active_production_line].production.values() if p < 0):
			for res, amount in self.production[self.active_production_line].production.items():
				if amount > 0:
					self.inventory.alter(res, amount)
			self.__used_resources = {}
			# ONLY DIFFERENCE TO PRIMARY PRODUCER HERE
			self._create_unit()
		if "idle_full" in horizons.main.action_sets[self._action_set_id].keys():
			self.act("idle_full", self._instance.getFacingLocation(), True)
		else:
			self.act("idle", self._instance.getFacingLocation(), True)

		if len(self.production_queue) > 0:
			# Start producing the next item in our production queue
			self.active_production_line = self.production_queue.pop()
			self.addChangeListener(self.check_production_startable)
			self.check_production_startable()
		else:
			# No more units in the queue, go inactive
			self.active_production_line = None
			self.toggle_active()

	def create_unit(self):
		"""Creates the specified unit at the buildings output point."""
		if self.output_point is None:
			for point in self.position.get_radius_coordinates(2):
				tile = self.island.get_tile(Point(point[0],point[1]))
				if isinstance(tile, horizons.main.session.entities.grounds[3]) or isinstance(tile, horizons.main.session.entities.grounds[2]):
					self.output_point = point
					break

		# Create the new units at the output_point
		for unit, amount in self.production[self.active_production_line].unit:
			horizons.main.session.entities.units[id](self.x, self.y, self.owner)


	def produce(self, prod_line):
		"""Called to start the UnitProducer's unit creation process.
		This should be used to start a production after the user has specified it.
		@param prod_line: id of the production line that is to be used.
		"""
		assert(prod_line in self.production.keys(), "ERROR: You specified an invalid production line!")
		if self.active:
			#Enqueue the new production, we are still producing.
			self.production_queue.append(prod_line)
		else:
			# Start production
			self.active_production_line = prod_line
			self.toggle_active()

class UnitProductionLine(object):

	def __init__(self, id):
		super(UnitProductionLine, self).__init__()
		self.id = id
		self.time = horizons.main.db("SELECT time FROM data.unit_production_line WHERE id=?", id)
		self.unit = horizons.main.db("SELECT unit FROM data.unit_production_line WHERE id=?", id)
		self.production = {}
		self.unit = {}
		for unit, amount in \
			horizons.main.db("SELECT unit, amount FROM data.production WHERE production_line=?", id):
			self.unit[unit] = amount
		for res, amount in \
			horizons.main.db("SELECT resource, amount FROM data.production WHERE production_line=?", id):
			self.production[amount] = amount