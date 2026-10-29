from typing import Dict, List, Optional, Tuple

from typing import Sequence


class LaneManager:
    """
    Manages the 4 approach regions of interest (NORTH, SOUTH, EAST, WEST)
    and the intersection box. Converts between normalized [0..1] coordinates
    and frame pixel coordinates.

    Each ROI is either:
      - an axis-aligned box  [x1, y1, x2, y2]  (normalized or absolute px > 1.0)
      - a 4-corner quad      [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]  (rotated / free-form)
    """
    def __init__(self, rois: Optional[Dict[str, list]] = None, intersection_box: Optional[List[float]] = None):
        # Default normalized coordinates [x1, y1, x2, y2]
        self.rois = rois or {
            "NORTH": [0.35, 0.00, 0.65, 0.40],
            "SOUTH": [0.35, 0.60, 0.65, 1.00],
            "WEST":  [0.00, 0.35, 0.40, 0.65],
            "EAST":  [0.60, 0.35, 1.00, 0.65],
        }
        self.intersection_box = intersection_box or [0.40, 0.40, 0.60, 0.60]

    def update_rois(self, new_rois: Dict[str, list], new_intersection: Optional[List[float]] = None):
        self.rois.update(new_rois)
        if new_intersection:
            self.intersection_box = new_intersection

    @staticmethod
    def is_quad(box: list) -> bool:
        """True when the box is a [[x,y],...] 4-corner polygon instead of [x1,y1,x2,y2]."""
        return (
            isinstance(box, (list, tuple))
            and len(box) == 4
            and all(isinstance(p, (list, tuple)) and len(p) == 2 for p in box)
        )

    def get_pixel_box(self, box: List[float], width: int, height: int) -> Tuple[int, int, int, int]:
        """Convert normalized [0..1] box to pixel coordinates [x1, y1, x2, y2]."""
        if self.is_quad(box):
            pts = self.get_pixel_polygon(box, width, height)
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            return min(xs), min(ys), max(xs), max(ys)
        # If coordinates are already > 1.0, treat as absolute pixels
        if max(box) > 1.0:
            return int(box[0]), int(box[1]), int(box[2]), int(box[3])
        return (
            int(box[0] * width),
            int(box[1] * height),
            int(box[2] * width),
            int(box[3] * height)
        )

    def get_pixel_polygon(self, box: list, width: int, height: int) -> List[Tuple[int, int]]:
        """Convert a ROI (axis box or quad) to a list of pixel corner points."""
        if self.is_quad(box):
            pts = []
            for p in box:
                px, py = p[0], p[1]
                if max(px, py) > 1.0:
                    pts.append((int(px), int(py)))
                else:
                    pts.append((int(px * width), int(py * height)))
            return pts
        x1, y1, x2, y2 = self.get_pixel_box(box, width, height)
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]

    @staticmethod
    def _point_in_polygon(cx: float, cy: float, poly: List[Tuple[int, int]]) -> bool:
        """Ray-casting point-in-polygon test (works for concave polygons too)."""
        inside = False
        n = len(poly)
        j = n - 1
        for i in range(n):
            xi, yi = poly[i]
            xj, yj = poly[j]
            if ((yi > cy) != (yj > cy)) and (cx < (xj - xi) * (cy - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    def is_inside_box(self, cx: float, cy: float, box: list, width: int, height: int) -> bool:
        if self.is_quad(box):
            return self._point_in_polygon(cx, cy, self.get_pixel_polygon(box, width, height))
        x1, y1, x2, y2 = self.get_pixel_box(box, width, height)
        return x1 <= cx <= x2 and y1 <= cy <= y2

    def is_in_intersection(self, cx: float, cy: float, width: int, height: int) -> bool:
        """Vehicles inside intersection center are crossing and should not be counted as waiting"""
        return self.is_inside_box(cx, cy, self.intersection_box, width, height)

    def classify_direction(
        self, cx: float, cy: float, width: int, height: int, fallback_nearest: bool = False
    ) -> Optional[str]:
        """
        Determines which approach direction the vehicle belongs to.
        Returns 'NORTH', 'SOUTH', 'EAST', 'WEST', or None.
        If fallback_nearest is True, calculates closest approach direction based on geometric quadrant.
        """
        for direction, box in self.rois.items():
            if self.is_inside_box(cx, cy, box, width, height):
                return direction
        if fallback_nearest and width > 0 and height > 0:
            nx = cx / width
            ny = cy / height
            dx = nx - 0.5
            dy = ny - 0.5
            if abs(dx) >= abs(dy):
                return "WEST" if dx < 0 else "EAST"
            else:
                return "NORTH" if dy < 0 else "SOUTH"
        return None