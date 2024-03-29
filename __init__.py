# -*- coding: utf-8 -*-

## @file __init__.py
# @date 2020
# @version 20.09
# @author Vincent MAJORCZYK
# @copyright Copyright 2020 CDI-Technologies (France), all right reserved.
# @par License:
# code released under GNU General Public License v3
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# @par CDI-Technologies:
# *23 avenue de la créativité, 59650 Villeneuve d'Ascq, France*
# https://cditech.fr/raies/
#
# @note this file was initialy generated by Plugin Builder (http://g-sherman.github.io/Qgis-Plugin-Builder/)

# noinspection PyPep8Naming

## @brief Load test class from file test.
# @param iface A QGIS interface instance.
def classFactory(iface):  # pylint: disable=invalid-name
    from .SuricatesPlugin import SuricatesPlugin
    return SuricatesPlugin(iface)
