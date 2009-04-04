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

import horizons.main

from horizons.world.production import SecondaryProducer, PrimaryProducer
from horizons.gui.tabwidget import TabWidget
from horizons.util.point import Point
from building import Building, Selectable
from buildable import BuildableSingleWithSurrounding, BuildableSingle


class AnimalFarm(Selectable, SecondaryProducer, BuildableSingleWithSurrounding, Building):
	_surroundingBuildingClass = 18
	""" This class builds pasturage in the radius automatically,
	so that farm animals can graze there """

	def __init__(self, **kwargs):
		super(AnimalFarm, self).__init__(**kwargs)

	def create_collector(self):
		self.animals = []

		# NOTE: animals have to be created before the AnimalCollector
		for (animal,number) in horizons.main.db("SELECT unit_id, count FROM data.animals \
		                                    WHERE building_id = ?", self.id):
			for i in xrange(0,number):
				horizons.main.session.entities.units[animal](self)
				# animal appends itself to self.animals

		# AnimalCollector:
		horizons.main.session.entities.units[7](self)

	def save(self, db):
		super(AnimalFarm, self).save(db)
		for animal in self.animals:
			animal.save(db)

	def load(self, db, worldid):
		super(AnimalFarm, self).load(db, worldid)
		self.animals = []


class Lumberjack(Selectable, SecondaryProducer, BuildableSingleWithSurrounding, Building):
	_surroundingBuildingClass = 17
	"""Class representing a Lumberjack."""

	def create_collector(self):
		"""Add a FieldCollector"""
		horizons.main.session.entities.units[10](self)


class Weaver(Selectable, SecondaryProducer, BuildableSingle, Building):

	def create_collector(self):
		"""Add a FieldCollector"""
		horizons.main.session.entities.units[12](self)


class Fisher(Selectable, PrimaryProducer, BuildableSingle, Building):

	def show_menu(self):
		horizons.main.session.ingame_gui.show_menu(TabWidget(4, object=self))

	@classmethod
	def isGroundBuildRequirementSatisfied(cls, x, y, island, **state):
		#todo: check cost line
		coast_tile_found = False
		for xx,yy in [ (xx,yy) for xx in xrange(x, x + cls.size[0]) for yy in xrange(y, y + cls.size[1]) ]:
			tile = island.get_tile(Point(xx,yy))
			classes = tile.__class__.classes
			if 'coastline' in classes:
				coast_tile_found = True
			elif 'constructible' not in classes:
				return None

		return {} if coast_tile_found else None

class Church(Selectable, PrimaryProducer, BuildableSingle, Building):
	pass