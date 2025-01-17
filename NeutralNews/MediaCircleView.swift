//
//  MediaCircleView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 1/10/25.
//

import SwiftUI

struct MediaCircleView: View {
    let media: PressMedia
    var color: Color {
        Color(media.name.normalized())
    }
    
    var body: some View {
        Image(media.name.normalized())
            .resizable()
            .scaledToFit()
            .frame(width: 24, height: 24)
            .padding(4)
            .background {
                Circle()
                    .fill(color)
            }
    }
}

#Preview {
    MediaCircleView(media: .mock)
}
