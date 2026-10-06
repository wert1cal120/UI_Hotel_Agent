"""Basic value-object invariants independent of the simulation runner."""

from datetime import date, timedelta
import unittest

from models import Booking, BookingStatus, Client, Hotel, Room, RoomStatus, RoomType


class ClientModelTests(unittest.TestCase):
    def setUp(self):
        self.arrival = date(2026, 9, 2)
        self.departure = self.arrival + timedelta(days=3)

    def test_request_uses_the_original_plain_class_interface(self):
        client = Client(
            "Guest", RoomType.DOUBLE, self.arrival, self.departure, request_id=17
        )
        self.assertEqual(client.name, "Guest")
        self.assertEqual(client.nights, 3)
        client.name = "Changed"
        self.assertEqual(client.name, "Changed")

    def test_dates_must_describe_a_positive_stay(self):
        for departure in (self.arrival, self.arrival - timedelta(days=1)):
            with self.subTest(departure=departure):
                with self.assertRaises(ValueError):
                    Client("Guest", RoomType.SINGLE, self.arrival, departure)

    def test_explicit_guest_count_is_preserved(self):
        client = Client(
            "Guest",
            RoomType.DOUBLE,
            self.arrival,
            self.departure,
            request_id=17,
            guests=1,
        )
        self.assertEqual(client.guests, 1)
        self.assertEqual(client.request_id, 17)

    def test_room_type_capacity_and_label_are_read_only(self):
        for room_type in RoomType:
            for field_name, replacement in (("capacity", 999), ("label", "Changed")):
                with self.subTest(room_type=room_type, field=field_name):
                    original = getattr(room_type, field_name)
                    with self.assertRaises(AttributeError):
                        setattr(room_type, field_name, replacement)
                    self.assertEqual(getattr(room_type, field_name), original)

    def test_original_hotel_booking_flow_and_room_calendar_are_preserved(self):
        hotel = Hotel()
        room = Room(0, RoomType.DOUBLE, RoomStatus.AVAILABLE)
        hotel.add_room(room)
        first = Client("First", RoomType.SINGLE, self.arrival, self.departure)
        booking = hotel.book_room(first, room)
        self.assertIsInstance(booking, Booking)
        self.assertIs(booking.room, room)
        self.assertEqual(room.bookings, [booking])
        self.assertEqual(hotel.clients, [first])
        overlapping = Client("Second", RoomType.SINGLE, self.arrival, self.departure)
        self.assertIsNone(hotel.book_room(overlapping, room))
        checkout_day = Client("Third", RoomType.SINGLE, self.departure,
                              self.departure + timedelta(days=1))
        self.assertIsNotNone(hotel.book_room(checkout_day, room))

    def test_cancelled_booking_does_not_block_the_original_availability_helper(self):
        room = Room(0, RoomType.SINGLE)
        guest = Client("First", RoomType.SINGLE, self.arrival, self.departure)
        booking = Booking(guest, room)
        booking.status = BookingStatus.CANCELLED
        self.assertTrue(Booking.check_availability(guest, room))


if __name__ == "__main__":
    unittest.main()
