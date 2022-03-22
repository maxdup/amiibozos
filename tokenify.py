import argparse
import re
import os
from dataclasses import dataclass

from typing import Optional, Iterable, Tuple, Generator, TextIO, Dict

import rapidtables as rt
import json

from svg_extrude.model import Scene, Shape, Group, ColorSet, Polygon, Point, Color
from svg_extrude import OutputWriter
from svg_extrude.scad import Renderer as ScadRenderer
from svg_extrude.scad import Writer as ScadWriter
from svg_extrude.scad import Identifier
from svg_extrude import css
from svg_extrude.util import group_by, identity, FactoryDict
from svg_extrude.util.text import pluralize
from svg_extrude.util.iter import filter_repetition
from svg_extrude.util.context import conditional_context
from libs import cjlano_svg as svg
from svg_extrude.css import extract_value
from svg_extrude.output_writer import ShapeNames, GroupNames, sanitize_identifier


def show_info(scene: Scene):
    table = []
    for group in scene.groups:
        name = group.color.display_name()
        shape_count = len(group.shapes)
        max_delta_e = max(shape.color.delta_e(group.color)
                          for shape in group.shapes)
        table.append({
            "prefix": "   ",
            "name": f"{name}:",
            "shape_count": f"{pluralize(shape_count, 'shape', 'shapes')},",
            "max_delta_e": f"max ΔE =",
            "max_delta_e_value": f"{max_delta_e:.2f}"
        })

    print("Groups:")
    print(rt.format_table(table, generate_header=False, separator=" "))


SCENE_HEIGHT = 0.48  # mm
PRECISION = 1
OVERLAY = None
FLIP = False


class TokenShape(Shape):
    # this override is only required to switch units to pt

    @classmethod
    def from_svg_path(cls, svg_path: svg.Path, precision: float, *, snap: Optional[float] = None, reverse: bool = False) -> "Shape":
        fill_rule = extract_value(svg_path.style, "fill-rule")
        if not (fill_rule is None or fill_rule == "evenodd"):
            logger.warning(
                "%s: fill rule %s not supported. Using evenodd instead.", svg_path.id, fill_rule)

        stroke = extract_value(svg_path.style, "stroke")
        if not (stroke is None or stroke == "none"):
            logger.warning(
                "%s: stroked paths are not supported. Ignoring stroke.", svg_path.id)

        fill = extract_value(svg_path.style, "fill") or "#000000"
        if fill:
            fill = Color.from_html(fill, None)

        px = 25.4e-3 / 72

        def length(v: float) -> float:
            v = v * px
            if snap:
                v = snap * round(v / snap)
            return v

        def point(svg_point) -> Point:
            if reverse:
                x = length(90 - svg_point.x)
            else:
                x = length(svg_point.x)
            y = length(svg_point.y)
            return Point(x, y)

        def path(segment) -> Tuple[Point]:
            return tuple(point(p) for p in filter_repetition(segment))
        segments = svg_path.segments(precision)
        paths = (path(segment) for segment in segments)
        polygon = Polygon(tuple(paths))

        return Shape(svg_path.id, fill, polygon)


@dataclass(frozen=True)
class TokenGroup(Group):
    # this override is only needed to add a group name
    name: str
    color: Color
    shapes: Tuple[Shape, ...]

    @classmethod
    def by_color(cls, shapes: Iterable[Shape], *, color_mapping=None, name="") -> Generator["TokenGroup", None, None]:

        def create_group(color: Color, group_shapes: Iterable[Shape]):
            tok = TokenGroup(color, tuple(group_shapes), name=name)
            return tok

        if color_mapping is None:
            color_mapping = identity

        grouped = group_by(shapes, lambda shape: color_mapping(shape.color))
        return (create_group(color, shapes) for color, shapes in grouped.items())


class TokenScene(Scene):
    @classmethod
    def from_svg(cls, file_name: str, *, precision: float, available_colors: Optional[ColorSet],
                 snap: Optional[float] = None, reverse: bool = False):
        svg_picture: svg.Svg = svg.parse(file_name)
        svg_paths = svg_picture.flatten()
        shapes = tuple(TokenShape.from_svg_path(path, precision, snap=snap, reverse=reverse)
                       for path in svg_paths)

        if available_colors:
            color_mapping = available_colors.closest
        else:
            color_mapping = None

        groups = tuple(TokenGroup.by_color(
            shapes, color_mapping=color_mapping, name=file_name))

        return cls(shapes=shapes, groups=groups)


def create_scene(filename, reverse=False):
    base_file = re.sub('.svg$', '', filename)
    scene = TokenScene.from_svg(
        filename, precision=PRECISION, available_colors=None, reverse=reverse)

    return scene


def render_base(writer):
    '''
    Equivalent to:

    difference() {
        cylinder(h=2.64, r=16);
        translate([0, 0, -1]) cylinder(h=1.48, r=14);
        translate([0, 0, 2.16]) cylinder(h=1.48, r=14);
        translate([0, 0, 1.2]) cylinder(h=0.24, r=13);
    }
    '''

    writer.scad_writer.blank_line()
    writer.scad_writer.comment("token base")

    with writer.scad_writer.translate([15.875, -15.875, -2.64]):
        with writer.scad_writer.difference():
            writer.scad_writer.print('cylinder(h=2.64, r=16, $fn=120);')

            with writer.scad_writer.translate([0, 0, -1]):
                writer.scad_writer.print('cylinder(h=1.48, r=14.4, $fn=120);')
            with writer.scad_writer.translate([0, 0, 2.16]):
                writer.scad_writer.print('cylinder(h=1.48, r=14.4, $fn=120);')
            with writer.scad_writer.translate([0, 0, 1.2]):
                writer.scad_writer.print('cylinder(h=0.24, r=13.6, $fn=120);')


class TokenGroupNames(GroupNames):
    def __init__(self, group: Group):
        name = sanitize_identifier(
            group.name + '_' + group.color.display_name())
        self.name = name
        self.group = Identifier(f"group_{name}")
        self.solid = Identifier(f"solid_{name}")


class TokenOutputWriter(OutputWriter):
    def __init__(self, file: TextIO):
        self.scad_writer = ScadWriter(file)
        self._shape_names: Dict[Shape, ShapeNames] = FactoryDict(ShapeNames)
        self._group_names: Dict[TokenGroup, GroupNames] = FactoryDict(TokenGroupNames)

    def write_groups(self, groups: Iterable[TokenGroup]):
        self.scad_writer.blank_line()
        self.scad_writer.comment("Groups")

        for group in groups:
            with self.scad_writer.define_module(self._group_names[group].group):
                # Implicit union
                for shape in group.shapes:
                    shape_names = self._shape_names[shape]
                    self.scad_writer.instance(shape_names.clipped_shape)


def render_faces(writer, scene_front, scene_back):
    thickness = 0.72
    overlay_thickness = 0.24
    flip = False

    # Write the definitions
    writer.write_points_and_paths(scene_front.shapes)
    writer.write_shapes(scene_front.shapes)
    writer.write_clipped_shapes(scene_front.shapes)
    writer.write_groups(scene_front.groups)
    writer.write_solids(scene_front.groups, height=thickness)

    with conditional_context(flip is not None, writer.flip(flip), None):
        writer.instantiate_groups(scene_front.groups, offset=0)

    writer.write_points_and_paths(scene_back.shapes)
    writer.write_shapes(scene_back.shapes)
    writer.write_clipped_shapes(scene_back.shapes)
    writer.write_groups(scene_back.groups)
    writer.write_solids(scene_back.groups, height=thickness)

    # Write the instantiations
    with conditional_context(flip is not None, writer.flip(flip), None):
        writer.instantiate_groups(scene_back.groups, offset=1.84)


def make_amiibozo(frontPath, backPath):
    
    scene_front = create_scene(os.path.join('svgs', frontPath))
    scene_back = create_scene(os.path.join('svgs', backPath), reverse=True)
    
    outName = re.sub('.svg$', '.stl', frontPath)
    outputName = os.path.join('models', outName)

    print(f"Rendering to {outputName}")
    with ScadRenderer().render_file(outputName, defines=None) as scad_file:
        writer = TokenOutputWriter(scad_file)
        render_base(writer)
        render_faces(writer, scene_front, scene_back)


if __name__ == "__main__":

    with open('config.json', "r") as f:
        data = json.loads(f.read())
        for series in data['series']:
            for front in series['frontsides']:

                make_amiibozo(front, series['backside'])

