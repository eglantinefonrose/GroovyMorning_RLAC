//
//  __GMFM_RadioFrance_DemoUITestsLaunchTests.swift
//  0.GMFM_RadioFrance_DemoUITests
//
//  Created by Eglantine Fonrose on 05/04/2026.
//

import XCTest

final class __GMFM_RadioFrance_DemoUITestsLaunchTests: XCTestCase {

    override class var runsForEachTargetApplicationUIConfiguration: Bool {
        true
    }

    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    @MainActor
    func testLaunch() throws {
        let app = XCUIApplication()
        app.launch()

        // Insert steps here to perform after app launch but before taking a screenshot,
        // such as logging into a test account or navigating somewhere in the app

        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = "Launch Screen"
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
