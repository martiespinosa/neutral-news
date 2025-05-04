//
//  NeutralNews.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 13/4/25.
//

import Foundation

struct NeutralNews: Codable, Hashable, Identifiable {
    static func == (lhs: NeutralNews, rhs: NeutralNews) -> Bool {
        lhs.group == rhs.group &&
        lhs.neutralTitle == rhs.neutralTitle &&
        lhs.neutralDescription == rhs.neutralDescription
    }
    
    func hash(into hasher: inout Hasher) {
        hasher.combine(group)
        hasher.combine(neutralTitle)
        hasher.combine(neutralDescription)
    }
    
    var id = UUID().uuidString
    let neutralTitle: String
    let neutralDescription: String
    let category: String
    let relevance: Int?
    let imageUrl: String?
    let imageMedium: String?
    let date: Date?
    let createdAt: Date
    let updatedAt: Date
    var group: Int
    
    static let mock = NeutralNews(
        neutralTitle: "Lorem ipsum dolor sit amet",
        neutralDescription: "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
        category: "Category",
        relevance: 3,
        imageUrl: "https://www.lavanguardia.com/files/og_thumbnail/files/fp/uploads/2025/04/22/68075b725f598.r_d.1714-2017-0.jpeg",
        imageMedium: "laVanguardia",
        date: .now,
        createdAt: .now,
        updatedAt: .now,
        group: 0
    )
}
