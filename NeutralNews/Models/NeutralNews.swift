//
//  NeutralNews.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 13/4/25.
//

import Foundation

struct NeutralNews: Codable, Identifiable {
    var id = UUID().uuidString
    let neutralTitle: String
    let neutralDescription: String
    let category: String
    let imageUrl: String?
    let createdAt: Date
    let updatedAt: Date
    var group: Int
    
    static let mock = NeutralNews(
        neutralTitle: "Lorem ipsum dolor sit amet",
        neutralDescription: "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
        category: "Category",
        imageUrl: "https://www.lavanguardia.com/files/og_thumbnail/files/fp/uploads/2025/04/22/68075b725f598.r_d.1714-2017-0.jpeg",
        createdAt: .now,
        updatedAt: .now,
        group: 0
    )
}
