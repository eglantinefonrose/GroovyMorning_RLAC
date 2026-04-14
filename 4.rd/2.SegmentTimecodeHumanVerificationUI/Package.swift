// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "SegmentTimecodeVerification",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "SegmentTimecodeVerification", targets: ["SegmentTimecodeVerification"])
    ],
    targets: [
        .executableTarget(
            name: "SegmentTimecodeVerification",
            path: "SegmentTimecodeVerification"
        )
    ]
)
