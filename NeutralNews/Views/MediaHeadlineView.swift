//
//  MediaHeadlineView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 1/4/25.
//

import SwiftUI

struct MediaHeadlineView: View {
    let news: News
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // TODO: Pedir permiso para usar los logos de los medios?
            if let uiImage = UIImage(named: news.sourceMedium.pressMedia.name.normalized()) {
                Image(uiImage: uiImage)
                    .resizable()
                    .scaledToFit()
                    .frame(height: 24)
            } else {
                Text(news.sourceMedium.pressMedia.name)
                    .font(.title2)
                    .fontWeight(.semibold)
//                    .fontDesign(.serif)
                    .foregroundColor(.secondary)
            }
            
            Text(news.title)
                .font(.title3)
                .fontWeight(.semibold)
                .fontDesign(.serif)
            
            Spacer()
            
            BiasScoreView(biasScore: news.neutralScore ?? 0)
        }
        .padding()  
        .frame(width: 220, height: 220)
        .background(.regularMaterial)
        .clipShape(.rect(cornerRadius: 20))
    }
}

#Preview {
    MediaHeadlineView(news: .mock)
}
