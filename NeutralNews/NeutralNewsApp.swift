//
//  NeutralNewsApp.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 12/17/24.
//

import SwiftUI
import FirebaseCore

@main
struct NeutralNewsApp: App {
    init() { FirebaseApp.configure() }
    
    var body: some Scene {
        WindowGroup {
            HomeView()
        }
    }
}
