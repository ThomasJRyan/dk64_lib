import unittest
from dataclasses import FrozenInstanceError

from dk64_lib.components.triangle import Triangle
from dk64_lib.components.vertex import Vertex
from dk64_lib.f3dex2.commands import G_TRI1, G_TRI2


class VertexTest(unittest.TestCase):
    def test_from_bytes(self):
        vertex = Vertex.from_bytes(
            b"\xff\xfe"
            + b"\x01\x02"
            + b"\x80\x00"
            + b"\x12\x34"
            + b"\x00\x10"
            + b"\x00\x20"
            + bytes((0x30, 0x40, 0x50, 0x60))
        )

        self.assertEqual(vertex.x, -2)
        self.assertEqual(vertex.y, 0x0102)
        self.assertEqual(vertex.z, -32768)
        self.assertEqual(vertex.unk, 0x1234)
        self.assertEqual(vertex.texture_cord_u, 0x10)
        self.assertEqual(vertex.texture_cord_v, 0x20)
        self.assertEqual(vertex.xr, 0x30)
        self.assertEqual(vertex.yg, 0x40)
        self.assertEqual(vertex.zb, 0x50)
        self.assertEqual(vertex.alpha, 0x60)

    def test_to_obj_line_includes_normalized_vertex_color(self):
        vertex = Vertex(
            -2,
            0x0102,
            -32768,
            0x1234,
            0x10,
            0x20,
            0x30,
            0x40,
            0x50,
            0x60,
        )

        self.assertEqual(
            vertex.to_obj_line(),
            "v -2 258 -32768 0.188235 0.250980 0.313725",
        )
        self.assertEqual(vertex.to_obj_line(include_color=False), "v -2 258 -32768")

    def test_is_frozen(self):
        vertex = Vertex.from_bytes(bytes(16))

        with self.assertRaises(FrozenInstanceError):
            vertex.x = 1


class TriangleTest(unittest.TestCase):
    def test_from_tri1(self):
        command = G_TRI1(b"\x05\x02\x04\x06\x00\x00\x00\x00")

        self.assertEqual(Triangle.from_tri1(command), Triangle(1, 2, 3))

    def test_from_tri2(self):
        command = G_TRI2(b"\x06\x02\x04\x06\x00\x08\x0a\x0c")

        self.assertEqual(
            Triangle.from_tri2(command),
            (Triangle(1, 2, 3), Triangle(4, 5, 6)),
        )

    def test_is_frozen(self):
        triangle = Triangle(1, 2, 3)

        with self.assertRaises(FrozenInstanceError):
            triangle.v1 = 4


if __name__ == "__main__":
    unittest.main()
