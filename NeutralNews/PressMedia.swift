//
//  PressMedia.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 1/5/25.
//

import Foundation
import SwiftUICore

struct PressMedia: Decodable {
    let name: String
    let link: String
    let imageName: String
    
    static let mock = PressMedia(
        name: "El País",
        link: "https://www.elpais.com",
        imageName: "elpais"
    )
}

enum Media: CaseIterable {
    case abc
    case elPais
    
    var pressMedia: PressMedia {
        switch self {
        case .elPais: return PressMedia(name: "El País", link: "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada", imageName: "elpais")
        case .abc: return PressMedia(name: "ABC", link: "https://www.abc.es/rss/2.0/portada/", imageName: "abc")
        }
    }
}

