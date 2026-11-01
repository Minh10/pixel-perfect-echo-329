"""Bounding-box helpers.  Internal representation: (l, t, r, b) in points, top-left origin."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas import BBox, NormalizedBBox


@dataclass(frozen=True)
class Box:
    l: float
    t: float
    r: float
    b: float

    @classmethod
    def from_bottom_left(cls, l: float, t: float, r: float, b: float, page_height: float) -> Box:
        """Convert a bottom-left-origin box (t > b, as Docling/PDF user space) to top-left origin."""
        top, bottom = page_height - max(t, b), page_height - min(t, b)
        return cls(min(l, r), top, max(l, r), bottom)

    @property
    def width(self) -> float:
        return max(0.0, self.r - self.l)

    @property
    def height(self) -> float:
        return max(0.0, self.b - self.t)

    @property
    def area(self) -> float:
        return self.width * self.height

    def clamp(self, width: float, height: float) -> Box:
        return Box(
            min(max(self.l, 0.0), width), min(max(self.t, 0.0), height),
            min(max(self.r, 0.0), width), min(max(self.b, 0.0), height),
        )

    def intersection_area(self, other: Box) -> float:
        w = min(self.r, other.r) - max(self.l, other.l)
        h = min(self.b, other.b) - max(self.t, other.t)
        return w * h if w > 0 and h > 0 else 0.0

    def fraction_inside(self, other: Box) -> float:
        """Share of *self*'s area that lies inside *other*."""
        return self.intersection_area(other) / self.area if self.area else 0.0

    def union(self, other: Box) -> Box:
        return Box(min(self.l, other.l), min(self.t, other.t), max(self.r, other.r), max(self.b, other.b))

    def to_schema(self) -> BBox:
        return BBox(l=round(self.l, 2), t=round(self.t, 2), r=round(self.r, 2), b=round(self.b, 2))

    def normalized(self, width: float, height: float) -> NormalizedBBox:
        c = self.clamp(width, height)
        return NormalizedBBox(
            x=round(c.l / width, 5), y=round(c.t / height, 5),
            width=round(c.width / width, 5), height=round(c.height / height, 5),
        )
