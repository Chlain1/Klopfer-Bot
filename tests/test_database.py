import unittest

import aiosqlite

from database import DatabaseManager


class TestDatabaseManager(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.connection = await aiosqlite.connect(":memory:")
        await self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS warns (
              id int(11) NOT NULL,
              user_id varchar(20) NOT NULL,
              server_id varchar(20) NOT NULL,
              moderator_id varchar(20) NOT NULL,
              reason varchar(255) NOT NULL,
              created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await self.connection.commit()
        self.manager = DatabaseManager(connection=self.connection)

    async def asyncTearDown(self):
        await self.connection.close()

    async def test_add_warn_increments_id(self):
        warn_id_1 = await self.manager.add_warn(1, 2, 3, "first")
        warn_id_2 = await self.manager.add_warn(1, 2, 3, "second")
        self.assertEqual(warn_id_1, 1)
        self.assertEqual(warn_id_2, 2)

    async def test_remove_warn_and_count(self):
        await self.manager.add_warn(1, 2, 3, "first")
        await self.manager.add_warn(1, 2, 3, "second")
        remaining = await self.manager.remove_warn(1, 1, 2)
        self.assertEqual(remaining, 1)

    async def test_get_warnings(self):
        await self.manager.add_warn(10, 20, 30, "reason")
        warnings = await self.manager.get_warnings(10, 20)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(str(warnings[0][0]), "10")
        self.assertEqual(str(warnings[0][1]), "20")
