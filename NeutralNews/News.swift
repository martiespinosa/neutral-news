//
//  News.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 12/17/24.
//

import Foundation

struct News: Decodable, Identifiable {
    var id = UUID()
    let title: String
    let description: String
    let category: String
    let link: String
    let pubDate: String
    let sourceMedium: PressMedia
    
    static let mock = News(
        title: "Title",
        description: "Description",
        category: "Category",
        link: "Link",
        pubDate: "PubDate",
        sourceMedium: .mock
    )
}
