-- 1. สร้างก้อน Database
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'ZoomBookingDB')
BEGIN
    CREATE DATABASE ZoomBookingDB;
END
GO

USE ZoomBookingDB;
GO

-- 2. สร้างตาราง User
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[User]') AND type in (N'U'))
BEGIN
    CREATE TABLE [User] (
        id INT PRIMARY KEY IDENTITY(1,1),
        username NVARCHAR(50) UNIQUE NOT NULL,
        password NVARCHAR(255) NOT NULL,
        role NVARCHAR(10) NOT NULL
    );
END

-- 3. สร้างตาราง Booking
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[Booking]') AND type in (N'U'))
BEGIN
    CREATE TABLE [Booking] (
        id INT PRIMARY KEY IDENTITY(1,1),
        requester_name NVARCHAR(100),
        department NVARCHAR(100),
        name NVARCHAR(255),
        room NVARCHAR(20),
        date NVARCHAR(10),
        start_time NVARCHAR(5),
        end_time NVARCHAR(5),
        username NVARCHAR(50)
    );
END

*****
จุดที่ต้องเช็กเรื่อง Admin เข้าไม่ได้ (ย้ำอีกครั้ง)
ถ้าคุณรัน app.py แล้วยังเข้า admin ไม่ได้ ให้รันคำสั่งนี้ใน SSMS เพื่อล้าง User เก่าที่อาจจะค้างอยู่ครับ:

USE ZoomBookingDB;
TRUNCATE TABLE [User];

*****
SQL สำหรับล้างข้อมูล (Maintenance)
เอาไว้ใช้เวลาเกิดปัญหา "รหัสผ่านไม่ถูกต้อง" หรืออยากล้างข้อมูลการจองทั้งหมดทิ้ง

-- ล้างข้อมูล User เพื่อให้ app.py สร้างให้ใหม่ตอนเริ่มรัน
DELETE FROM [User];
-- ล้างข้อมูลการจองทั้งหมด
DELETE FROM [Booking];